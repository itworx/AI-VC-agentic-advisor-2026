"""
SP-01: fetch-and-read-a-page utility.

Given a URL, return usable page text or a clear, typed reason why not.
Never raises -- every failure is captured in the returned FetchResult so a
LangGraph node can call this directly without a try/except around it.
"""
from typing import Literal, Optional

import requests
import trafilatura
from pydantic import BaseModel

FetchStatus = Literal["ok", "unreachable", "http_error", "no_text_content"]

MIN_TEXT_LENGTH = 200
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class FetchResult(BaseModel):
    url: str
    status: FetchStatus
    text: Optional[str] = None
    status_code: Optional[int] = None
    reason: Optional[str] = None


def fetch_page(url: str) -> FetchResult:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        return FetchResult(
            url=url,
            status="unreachable",
            reason=f"{type(exc).__name__}: {exc}",
        )

    if not response.ok:
        return FetchResult(
            url=url,
            status="http_error",
            status_code=response.status_code,
            reason=f"HTTP {response.status_code}",
        )

    extracted_text = trafilatura.extract(response.text)

    if not extracted_text or len(extracted_text.strip()) < MIN_TEXT_LENGTH:
        return FetchResult(
            url=url,
            status="no_text_content",
            status_code=response.status_code,
            reason="No extractable article text (JS-only, image-only, or bot-wall page)",
        )

    return FetchResult(
        url=url,
        status="ok",
        status_code=response.status_code,
        text=extracted_text,
    )
