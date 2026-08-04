"""
Unit tests for fetch_service's SSRF protections (S-04). These are
rejected before any network call is made (scheme check, or DNS
resolution of a literal/loopback address), so no `network` marker needed.
"""
from backend.services.fetch_service import fetch_page


def test_ftp_scheme_is_blocked():
    result = fetch_page("ftp://example.com/file.txt")
    assert result.status == "blocked"


def test_file_scheme_is_blocked():
    result = fetch_page("file:///etc/passwd")
    assert result.status == "blocked"


def test_loopback_ip_is_blocked():
    result = fetch_page("http://127.0.0.1/admin")
    assert result.status == "blocked"


def test_localhost_hostname_is_blocked():
    result = fetch_page("http://localhost:8080/")
    assert result.status == "blocked"


def test_link_local_metadata_ip_is_blocked():
    # The classic SSRF target: cloud provider instance-metadata endpoints.
    result = fetch_page("http://169.254.169.254/latest/meta-data/")
    assert result.status == "blocked"


def test_private_rfc1918_ip_is_blocked():
    result = fetch_page("http://10.0.0.5/internal")
    assert result.status == "blocked"


def test_private_192_range_is_blocked():
    result = fetch_page("http://192.168.1.1/router")
    assert result.status == "blocked"
