from __future__ import annotations
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from backend.models.categories import ALLOWED_CATEGORIES, REQUIRED_CATEGORIES
from backend.models.claim import Claim, ClaimContent, SpecialistOutput

# Helpers


def _valid_content_dict() -> dict:
    """A dict that constructs a valid ClaimContent (no timestamp)."""
    return {
        "claim_text": "Acme Corp raised a $2M seed round in 2023.",
        "source_url": "https://example.com/acme-funding",
        "quoted_snippet": "Acme announced a $2M seed round in Q3 2023.",
        "specialist": "team_signals",
        "confidence": "reported",
        "category": "funding_stage",
    }


def _valid_claim_dict() -> dict:
    """A dict that constructs a valid Claim (adds a retrieval_timestamp)."""
    return {
        **_valid_content_dict(),
        "retrieval_timestamp": datetime.now(tz=timezone.utc),
    }



# C-03: A claim without a source URL is rejected.


def test_claim_without_source_url_is_rejected():
    """C-03: schema must reject any claim missing source_url."""
    data = _valid_claim_dict()
    del data["source_url"]

    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_with_empty_source_url_is_rejected():
    """An empty string is not a valid URL."""
    data = _valid_claim_dict()
    data["source_url"] = ""

    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_with_malformed_source_url_is_rejected():
    """A non-URL string is not a valid URL."""
    data = _valid_claim_dict()
    data["source_url"] = "not-a-url"

    with pytest.raises(ValidationError):
        Claim(**data)


# Other required fields

def test_claim_missing_claim_text_is_rejected():
    data = _valid_claim_dict()
    del data["claim_text"]
    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_with_empty_claim_text_is_rejected():
    data = _valid_claim_dict()
    data["claim_text"] = ""
    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_missing_quoted_snippet_is_rejected():
    data = _valid_claim_dict()
    del data["quoted_snippet"]
    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_missing_specialist_is_rejected():
    data = _valid_claim_dict()
    del data["specialist"]
    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_missing_confidence_is_rejected():
    data = _valid_claim_dict()
    del data["confidence"]
    with pytest.raises(ValidationError):
        Claim(**data)


def test_claim_missing_category_is_rejected():
    data = _valid_claim_dict()
    del data["category"]
    with pytest.raises(ValidationError):
        Claim(**data)


# Field constraints

def test_quoted_snippet_over_25_words_is_rejected():
    data = _valid_claim_dict()
    data["quoted_snippet"] = " ".join(["word"] * 26)  # 26 words
    with pytest.raises(ValidationError):
        Claim(**data)


def test_quoted_snippet_at_25_words_is_accepted():
    data = _valid_claim_dict()
    data["quoted_snippet"] = " ".join(["word"] * 25)  # exactly 25
    claim = Claim(**data)
    assert len(claim.quoted_snippet.split()) == 25


def test_invalid_specialist_is_rejected():
    data = _valid_claim_dict()
    data["specialist"] = "not_a_real_specialist"
    with pytest.raises(ValidationError):
        Claim(**data)


def test_invalid_confidence_is_rejected():
    data = _valid_claim_dict()
    data["confidence"] = "very_sure"
    with pytest.raises(ValidationError):
        Claim(**data)


def test_category_not_in_allowed_is_rejected():
    data = _valid_claim_dict()
    data["category"] = "made_up_category"
    with pytest.raises(ValidationError):
        Claim(**data)


def test_all_allowed_categories_actually_validate():
    """Every value in ALLOWED_CATEGORIES must construct a valid Claim."""
    for cat in ALLOWED_CATEGORIES:
        data = _valid_claim_dict()
        data["category"] = cat
        # Should not raise
        Claim(**data)


# Happy path

def test_fully_valid_claim_is_accepted():
    """A fully populated claim with valid fields passes validation."""
    claim = Claim(**_valid_claim_dict())
    assert claim.category in ALLOWED_CATEGORIES
    assert str(claim.source_url).startswith("http")


def test_retrieval_timestamp_auto_populates_when_omitted():
    """If a specialist forgets retrieval_timestamp, the factory sets it."""
    data = _valid_claim_dict()
    del data["retrieval_timestamp"]
    claim = Claim(**data)
    assert claim.retrieval_timestamp is not None
    # Should be timezone-aware UTC
    assert claim.retrieval_timestamp.tzinfo is not None


# SpecialistOutput wrapper

def test_specialist_output_accepts_empty_lists():
    """A specialist may return no claims and no not_found; valid response."""
    output = SpecialistOutput()
    assert output.claims == []
    assert output.not_found == []


def test_specialist_output_rejects_bad_not_found_category():
    with pytest.raises(ValidationError):
        SpecialistOutput(claims=[], not_found=["not_a_real_category"])


def test_specialist_output_with_claims_and_not_found():
    output = SpecialistOutput(
        claims=[Claim(**_valid_claim_dict())],
        not_found=["market_trends", "public_statements"],
    )
    assert len(output.claims) == 1
    assert "market_trends" in output.not_found


# ClaimContent (LLM-facing, no retrieval_timestamp)

def test_claim_content_has_no_retrieval_timestamp_field():
    """S-02: ClaimContent must not expose retrieval_timestamp to the LLM."""
    fields = ClaimContent.model_fields
    assert "retrieval_timestamp" not in fields, (
        "retrieval_timestamp on ClaimContent would let the LLM invent it"
    )


def test_claim_content_constructs_without_timestamp():
    """ClaimContent takes 6 fields; no timestamp needed."""
    content = ClaimContent(**_valid_content_dict())
    assert content.category == "funding_stage"


def test_claim_inherits_content_fields_and_adds_timestamp():
    """Claim has everything ClaimContent has, plus retrieval_timestamp."""
    claim = Claim(**_valid_claim_dict())
    assert claim.category == "funding_stage"
    assert claim.retrieval_timestamp is not None


# Sanity check on categories

def test_required_is_subset_of_allowed():
    """REQUIRED_CATEGORIES must be a subset of ALLOWED_CATEGORIES."""
    assert REQUIRED_CATEGORIES.issubset(ALLOWED_CATEGORIES)


def test_required_categories_not_empty():
    """If REQUIRED is empty, check_coverage would always say 'done' immediately."""
    assert len(REQUIRED_CATEGORIES) > 0