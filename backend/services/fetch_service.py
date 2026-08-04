"""
SP-01: fetch-and-read-a-page utility.

Given a URL, return usable page text or a clear, typed reason why not.
Never raises -- every failure is captured in the returned FetchResult so a
LangGraph node can call this directly without a try/except around it.
"""
import ipaddress
import socket
import time
from typing import Literal, Optional
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from pydantic import BaseModel

FetchStatus = Literal["ok", "unreachable", "http_error", "no_text_content", "blocked"]

MIN_TEXT_LENGTH = 200
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_DOWNLOAD_SECONDS = REQUEST_TIMEOUT_SECONDS * 3
ALLOWED_SCHEMES = {"http", "https"}


class FetchResult(BaseModel):
    url: str
    status: FetchStatus
    text: Optional[str] = None
    status_code: Optional[int] = None
    reason: Optional[str] = None


def _is_safe_host(hostname: str) -> bool:
    """S-04: reject hosts that resolve to loopback/link-local/private/
    reserved ranges, so a search result (or a redirect target) can't be
    used to reach internal infrastructure like a cloud metadata endpoint.

    Known residual gap: this validates the hostname at check-time: a
    DNS-rebinding attacker who controls the domain could in principle
    return a different (unsafe) IP by the time `requests` itself
    resolves and connects. Defending that fully needs IP-pinning the
    actual connection, which is more machinery than this project's
    threat model (search-result and redirect URLs) calls for -- noted
    here rather than silently ignored.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        # Can't resolve at all -- not a safety concern, just means the
        # actual request will fail naturally and surface as "unreachable"
        # rather than "blocked".
        return True

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    if not parsed.hostname:
        return False
    return _is_safe_host(parsed.hostname)


def _fetch_with_manual_redirects(url: str):
    """Follows redirects one hop at a time, re-validating each target
    before following it -- requests' default allow_redirects=True would
    follow anywhere, including a hop straight into a private IP that the
    original URL never suggested."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_safe_url(current_url):
            return None, "blocked_url"

        response = requests.get(
            current_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
            stream=True,
        )

        if response.is_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                return response, None
            current_url = urljoin(current_url, location)
            continue

        return response, None

    return None, "too_many_redirects"


def _read_body_with_caps(response) -> Optional[bytes]:
    """Streams the body with a byte cap and a wall-clock cap, instead of
    letting a huge or slow-drip response be read in full before we
    notice. Returns None if either cap is exceeded."""
    body = bytearray()
    started = time.monotonic()
    for chunk in response.iter_content(chunk_size=8192):
        if time.monotonic() - started > MAX_DOWNLOAD_SECONDS:
            return None
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            return None
    return bytes(body)


def fetch_page(url: str) -> FetchResult:
    if not _is_safe_url(url):
        return FetchResult(
            url=url,
            status="blocked",
            reason="URL scheme not allowed, or host resolves to a private/loopback/link-local address",
        )

    try:
        response, block_reason = _fetch_with_manual_redirects(url)
    except requests.exceptions.RequestException as exc:
        return FetchResult(
            url=url,
            status="unreachable",
            reason=f"{type(exc).__name__}: {exc}",
        )

    if block_reason == "blocked_url":
        return FetchResult(url=url, status="blocked", reason="Redirected to a disallowed host")
    if block_reason == "too_many_redirects":
        return FetchResult(url=url, status="unreachable", reason=f"Exceeded {MAX_REDIRECTS} redirects")

    if not response.ok:
        status_code = response.status_code
        response.close()
        return FetchResult(
            url=url,
            status="http_error",
            status_code=status_code,
            reason=f"HTTP {status_code}",
        )

    status_code = response.status_code
    body = _read_body_with_caps(response)
    response.close()

    if body is None:
        return FetchResult(
            url=url,
            status="blocked",
            status_code=status_code,
            reason=f"Response exceeded the {MAX_RESPONSE_BYTES}-byte or {MAX_DOWNLOAD_SECONDS}s download cap",
        )

    html = body.decode(response.encoding or "utf-8", errors="replace")
    extracted_text = trafilatura.extract(html)

    if not extracted_text or len(extracted_text.strip()) < MIN_TEXT_LENGTH:
        return FetchResult(
            url=url,
            status="no_text_content",
            status_code=status_code,
            reason="No extractable article text (JS-only, image-only, or bot-wall page)",
        )

    return FetchResult(
        url=url,
        status="ok",
        status_code=status_code,
        text=extracted_text,
    )
