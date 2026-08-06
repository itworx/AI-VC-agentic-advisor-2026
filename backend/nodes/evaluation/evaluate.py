"""
E-01 / E-02 / E-03

The evaluator. Checks that every sentence in the memo draft traces back to a
claim in the claims list, rejects with feedback naming the specific offending
sentences, and stops after EVALUATOR_CAP passes so a stubborn model can't
loop forever.

Two tiers:

  Tier 1 (this module, pure Python): is there a citation marker, and does it
    resolve to a real claim? Deterministic, free, offline, and authoritative -
    nothing downstream can clear a tier-1 finding.
  Tier 2 (support.py, one model call): does the cited claim actually SAY what
    the sentence says? Tier 1 cannot answer this, because entailment is not a
    string operation, and without it a model satisfies the evaluator completely
    by spraying plausible markers onto unsupported sentences.

Tier 1 is the floor precisely because it can't be argued with. Tier 2 is the
part that needs a model, so it's isolated in its own module, sees only the
sentence and its cited claim text, and can only ever ADD violations.

Where it runs in the pipeline:
    write_memo -> evaluate -> [reject] -> back to write_memo with feedback
                           -> [accept] -> render_citations -> END
Evaluate reads the RAW draft sections (memo_bull/memo_base/memo_bear), whose
<<N>> markers point straight at claim indices, and writes no memo text at all -
this node judges, render_citations presents. Running before the renderer is what
makes an out-of-range <<N>> a clean reject rather than an
UnresolvedCitationError thrown from inside render_citations.

An unmarked sentence is BLOCKING by default. Only two things excuse one: a
statement that information could not be found (there is no claim to cite for a
gap), or a statement about this memo's own reasoning rather than about the
company. Everything else must carry a marker. See _META_PATTERNS for why the
default runs this way round rather than trying to detect which sentences look
factual.

What this catches and what it doesn't:
  CATCHES  any uncited assertion about the company - the invented market size
           / customer count / team size case, and equally the uncited product
           or positioning claim that carries no numbers at all.
  CATCHES  a citation pointing at a claim index that doesn't exist.
  FLAGS    a citation that shares no vocabulary with the claim it points at.
  DOESN'T  judge whether a cited claim genuinely supports the sentence's
           argument. Marker presence is not semantic entailment. That
           judgement stays with the human read-through in I-05.
"""

from __future__ import annotations

import re

from backend.models.claim import Claim
from backend.models.evaluation import EvaluationResult, Section, Violation
from backend.models.memo import MemoDraft
from backend.nodes.evaluation.support import SupportCheckError

# E-03: how many times evaluate may run for one memo. Hitting the cap means we
# ship the draft with a warning rather than rewriting forever - see evaluate().
EVALUATOR_CAP = 2

# How many advisory violations to print per pass. They're informational, and a
# memo citing many claims can generate dozens; all of them go onto state.
_ADVISORY_LOG_LIMIT = 5

CITATION_PATTERN = re.compile(r"<<(\d+)>>")

_SENTENCE_END = re.compile(r"[.!?]+")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")

# Periods that don't end a sentence. Checked as "last whitespace-delimited
# token + the matched punctuation", lowercased.
_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "u.s.", "u.k.", "e.g.", "i.e.", "etc.", "vs.", "approx.", "est.",
        "no.", "inc.", "ltd.", "co.", "corp.", "llc.", "plc.", "al.",
        "fig.", "cf.", "ca.", "yr.", "q1.", "q2.", "q3.", "q4.",
    }
)

# Sentences that talk about the MEMO rather than the company: "the bear case
# rests on...", "the claims gathered do not cover...". These are the only
# unmarked sentences treated as non-blocking, because they assert nothing about
# the company that could be true or false.
#
# This list is deliberately an allowlist of *memo-structural* vocabulary, which
# is small and closed. An earlier version inverted the test - an allowlist of
# "factual-sounding" words (revenue, market, headcount...) with everything else
# assumed connective - and a live run (tests/manual/test_evaluate_live.py)
# walked straight through it: "Instabug provides mobile app monitoring and bug
# reporting tools for developers" contains no finance vocabulary at all, so an
# uncited product claim scored as merely advisory. Any allowlist of factual
# words has that hole, because the set of things a company can factually do is
# unbounded. The set of ways to refer to this memo's own reasoning is not.
#
# So: unmarked is BLOCKING by default. When this heuristic is wrong the cost is
# a rework cycle on a sentence that didn't need one. When the old one was
# wrong, an uncited assertion shipped. Only one of those is acceptable.
_META_PATTERNS: tuple[str, ...] = (
    "bull case",
    "base case",
    "bear case",
    "this memo",
    "the memo",
    "the claims",
    "these claims",
    "available claims",
    "claims gathered",
    "the available information",
    "this analysis",
    "the analysis",
    "in evaluating",
    "the following",
)

# Sentences that assert the ABSENCE of information. write_memo.txt asks for
# these explicitly ("say so rather than guessing"), and there is by definition
# no claim to cite for a gap, so they're allowed unmarked. Digits/currency in
# the same sentence override this - see _classify().
#
# Detected as a NEGATION word followed closely by an INFORMATION word, rather
# than as a list of literal phrases. Two live runs each added a phrase the list
# didn't have ("absent verified data on customer count...", then "the absence of
# any traction or financial claims..."), which is the signature of a rule
# enumerated at the wrong level. Memos have many ways to say "we don't know
# this" and only so many words for the knowing.
#
# The pairing is what keeps it honest. A bare negation word would exempt far too
# much: "Absent serious competitors, Instabug dominates the market" is an
# unsourced assertion about the company, not a statement about a gap - and
# "competitors" is not an information word, so it stays blocking.
_NEGATION_WORDS = r"(?:no|not|never|nothing|absent|absence|lack|lacks|lacking|without)"
_INFORMATION_WORDS = r"(?:data|information|claims?|disclosur\w*|disclosed|figures?|evidence|traction|details?|metrics?|numbers?|transparency|visibility|records?|basis|reported|stated|available|found|covered|verified|published|publicly|breakdown|guidance|signals?)"

# These mean "this information does not exist" on their own - "headcount is
# undisclosed" needs no second word to be a gap statement.
_STANDALONE_ABSENCE = (
    r"\b(?:undisclosed|unavailable|unverified|unreported|unspecified|"
    r"unquantified|unknown)\b"
)

# Either a standalone absence word, or a negation word followed closely by an
# information word. The 60-char window never crosses a sentence boundary, so a
# "no." at the end of one clause can't chain into an exemption for the next.
_ABSENCE_RE = re.compile(
    rf"{_STANDALONE_ABSENCE}"
    rf"|\b{_NEGATION_WORDS}\b[^.!?]{{0,60}}?\b{_INFORMATION_WORDS}\b",
    re.IGNORECASE,
)

# Kept as literal phrases because they don't fit the negation->information
# shape: they name the claims list itself as the thing that fell short.
_ABSENCE_PHRASES: tuple[str, ...] = (
    "could not be",
    "among the claims",
    "from the available claims",
    "in the claims gathered",
)

_CURRENCY = frozenset("$€£¥%")

_STOPWORDS: frozenset[str] = frozenset(
    {
        "that", "this", "with", "from", "have", "has", "been", "were", "was",
        "which", "their", "there", "these", "those", "than", "then", "into",
        "about", "would", "could", "should", "also", "more", "most", "over",
        "under", "while", "however", "although", "because", "being", "other",
        "some", "such", "only", "very", "much", "many", "both", "each",
        "case", "memo", "company", "companys", "claims", "claim",
    }
)

# A sentence needs at least this many content words before weak-support
# overlap checking is meaningful. Below it, "no overlap" means nothing.
_MIN_CONTENT_WORDS_FOR_OVERLAP = 3


def split_sentences(text: str) -> list[str]:
    """Split memo text into sentences, conservatively.

    Markdown headings are dropped (they aren't assertions). Bullet items are
    treated as sentences even without terminal punctuation, because a memo
    bullet like "- 40% YoY growth" is exactly the kind of unsourced figure
    this evaluator exists to catch, and a naive split on "." would miss it
    entirely.

    Splits on . ! ? but not on decimals ("$1.2M"), initials, or the
    abbreviations in _ABBREVIATIONS.
    """
    sentences: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lstrip().startswith("#"):
            continue
        line = _LIST_MARKER.sub("", line, count=1)
        sentences.extend(_split_line(line))
    return sentences


def _split_line(line: str) -> list[str]:
    out: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(line):
        end = match.end()
        if end >= len(line):
            break  # trailing punctuation; the tail below picks it up
        if not line[end].isspace():
            continue  # decimal point, "U.S", version number, etc.
        preceding = line[start : match.start()].split()
        token = preceding[-1].lower() if preceding else ""
        if token + match.group(0) in _ABBREVIATIONS:
            continue
        if len(token) == 1 and token.isalpha():
            continue  # single initial
        piece = line[start:end].strip()
        if piece:
            out.append(piece)
        start = end
    tail = line[start:].strip()
    if tail:
        out.append(tail)
    return out


def _content_words(text: str) -> set[str]:
    stripped = CITATION_PATTERN.sub(" ", text).lower()
    words = re.findall(r"[a-z][a-z0-9]{3,}", stripped)
    return {w for w in words if w not in _STOPWORDS}


def _has_quantitative_signal(sentence: str) -> bool:
    """Digits or currency. Checked first and overrides everything: a sentence
    carrying a figure needs a source no matter how it's phrased."""
    return any(ch.isdigit() for ch in sentence) or any(
        ch in _CURRENCY for ch in sentence
    )


def _states_absence(sentence: str) -> bool:
    if _ABSENCE_RE.search(sentence):
        return True
    lowered = sentence.lower()
    return any(pat in lowered for pat in _ABSENCE_PHRASES)


def _is_meta_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(pat in lowered for pat in _META_PATTERNS)


def _classify(sentence: str, section: Section, claims: list[Claim]) -> Violation | None:
    """Return a Violation for this sentence, or None if it traces cleanly."""
    cited_ids = [int(n) for n in CITATION_PATTERN.findall(sentence)]

    if cited_ids:
        out_of_range = sorted({n for n in cited_ids if n < 1 or n > len(claims)})
        if out_of_range:
            return Violation(
                section=section,
                sentence=sentence,
                kind="unresolved_citation",
                cited_ids=cited_ids,
                detail=(
                    f"cites {', '.join(f'<<{n}>>' for n in out_of_range)}, which "
                    f"is not a claim - the list has {len(claims)} claims, so "
                    f"valid markers are <<1>> to <<{len(claims)}>>"
                ),
            )

        sentence_words = _content_words(sentence)
        if len(sentence_words) >= _MIN_CONTENT_WORDS_FOR_OVERLAP:
            cited_words: set[str] = set()
            for n in cited_ids:
                cited_words |= _content_words(claims[n - 1].claim_text)
            if cited_words and not (sentence_words & cited_words):
                return Violation(
                    section=section,
                    sentence=sentence,
                    kind="weak_support",
                    cited_ids=cited_ids,
                    detail=(
                        "shares no wording with the claim(s) it cites - check "
                        "the marker points at the right claim"
                    ),
                )
        return None

    # No citation marker at all. Order matters: a figure needs a source
    # however the sentence is worded, so the quantitative check comes first
    # and neither exemption below can override it.
    if not _has_quantitative_signal(sentence):
        if _states_absence(sentence):
            # A legitimate "we couldn't find this" statement. Nothing to cite.
            return None
        if _is_meta_sentence(sentence):
            return Violation(
                section=section,
                sentence=sentence,
                kind="untraced",
                detail=(
                    "no citation marker, but reads as a statement about this "
                    "memo's own reasoning rather than about the company, so "
                    "not blocking - check it isn't smuggling in an assertion"
                ),
            )

    return Violation(
        section=section,
        sentence=sentence,
        kind="untraced_factual",
        detail=(
            "asserts something about the company with no citation marker - "
            "either add the <<N>> of the claim that supports it, or delete "
            "the sentence. Do not cite a claim that doesn't actually say this"
        ),
    )


def _sections(memo: MemoDraft) -> list[tuple[Section, str]]:
    return [
        ("bull_case", memo.bull_case),
        ("base_case", memo.base_case),
        ("bear_case", memo.bear_case),
    ]


def trace_memo(memo: MemoDraft, claims: list[Claim]) -> EvaluationResult:
    """E-01 tier 1. Pure Python: marker presence and resolvability.

    Use evaluate_memo() for the full check - this is the deterministic floor,
    exposed on its own because every one of its findings is reproducible without
    a model and it is what the unit tests pin down.
    """
    violations: list[Violation] = []
    checked = 0
    traced = 0

    for section, text in _sections(memo):
        for sentence in split_sentences(text):
            checked += 1
            violation = _classify(sentence, section, claims)
            if violation is None:
                traced += 1
            else:
                violations.append(violation)

    blocking = [v for v in violations if v.blocking]
    return EvaluationResult(
        passed=not blocking,
        violations=violations,
        sentences_checked=checked,
        sentences_traced=traced,
    )


def _cited_pairs(
    memo: MemoDraft, claims: list[Claim]
) -> list[tuple[Section, str, list[int], list[Claim]]]:
    """Every sentence whose markers all resolve, with the claims it cites.

    Sentences with unresolved markers are excluded: tier 1 already blocks them,
    and there is no claim text to judge them against.
    """
    out = []
    for section, text in _sections(memo):
        for sentence in split_sentences(text):
            ids = [int(n) for n in CITATION_PATTERN.findall(sentence)]
            if not ids or any(n < 1 or n > len(claims) for n in ids):
                continue
            out.append((section, sentence, ids, [claims[n - 1] for n in ids]))
    return out


def evaluate_memo(
    memo: MemoDraft,
    claims: list[Claim],
    support_checker=None,
) -> EvaluationResult:
    """E-01, both tiers.

    support_checker: callable taking [(sentence, cited_claims)] and returning
        {index: (supported, reason)} - i.e. check_support's signature. None runs
        tier 1 only, which is what the unit tests do and what a caller should
        pass when they want a free, fully deterministic check.

    Tier 2 can only add violations. A model verdict never clears a tier-1
    finding, so no amount of agreeable judging can unblock a sentence that
    carries no citation.
    """
    result = trace_memo(memo, claims)
    if support_checker is None:
        return result

    pairs = _cited_pairs(memo, claims)
    if not pairs:
        return result

    verdicts = support_checker([(sentence, cited) for _, sentence, _, cited in pairs])

    extra: list[Violation] = []
    for i, (section, sentence, ids, _cited) in enumerate(pairs):
        supported, reason = verdicts.get(i, (False, "no verdict returned"))
        if supported:
            continue
        extra.append(
            Violation(
                section=section,
                sentence=sentence,
                kind="unsupported_by_claim",
                cited_ids=ids,
                detail=(
                    f"cites {', '.join(f'<<{n}>>' for n in ids)} but those "
                    f"claims do not support it: {reason.strip() or 'unspecified'}"
                    ". Cite a claim that does say this, weaken the sentence to "
                    "what the claim actually supports, or delete it"
                ),
            )
        )

    if not extra:
        return result

    # A sentence flagged by tier 2 is no longer "traced", even though tier 1
    # counted it as such. Recount from scratch rather than subtracting: a
    # sentence can collect a violation from BOTH tiers (weak_support from tier 1
    # and unsupported_by_claim from tier 2 tend to fire together, since a
    # citation pointing at the wrong claim usually shares no vocabulary with
    # it), and subtracting would count it twice and undercount the total.
    all_violations = result.violations + extra
    flagged = {(v.section, v.sentence) for v in all_violations}
    return EvaluationResult(
        passed=not [v for v in all_violations if v.blocking],
        violations=all_violations,
        sentences_checked=result.sentences_checked,
        sentences_traced=max(0, result.sentences_checked - len(flagged)),
    )


def format_feedback(result: EvaluationResult, claims: list[Claim]) -> str:
    """E-02. Reject with specific feedback naming the offending sentences.

    Quotes each one verbatim. A rewrite instruction that says "some sentences
    were untraced" gives the model nothing to act on; naming them is the
    whole point of this task.
    """
    blocking = result.blocking_violations
    advisory = result.advisory_violations

    lines = [
        "The previous draft was REJECTED by the evaluator.",
        "",
        f"{len(blocking)} sentence(s) do not trace to any claim in the claims "
        f"list. Every one must be fixed:",
        "",
    ]
    for i, v in enumerate(blocking, start=1):
        lines.append(f'{i}. [{v.section}] "{v.sentence}"')
        lines.append(f"   -> {v.detail}")
        lines.append("")

    if advisory:
        lines.append(
            f"Also worth a second look ({len(advisory)}, not blocking on their own):"
        )
        for v in advisory:
            lines.append(f'  - [{v.section}] "{v.sentence}" -> {v.detail}')
        lines.append("")

    lines.extend(
        [
            "Rules for the rewrite:",
            f"- You have {len(claims)} claims. Valid markers are <<1>> to "
            f"<<{len(claims)}>>. Never cite outside that range.",
            "- Do not fix a sentence by attaching a marker to a claim that "
            "doesn't actually support it. Deleting the sentence, or replacing "
            "it with an explicit statement that the information wasn't found, "
            "is always the correct fix when no claim covers it.",
            "- Keep everything the evaluator did not flag. This is a revision, "
            "not a fresh draft.",
        ]
    )
    return "\n".join(lines)


def _evaluate_impl(state, support_checker) -> dict:
    """E-01 + E-02 + E-03. See make_evaluate_node for the public entry point.

    Sets evaluator_decision for the router:

      "accept"        - clean, or nothing to check.
      "rewrite"       - blocking violations and we're under the cap. Feedback
                        goes to write_memo, which loops.
      "accept_capped" - blocking violations but the cap is spent. We ship, and
                        render_citations says so loudly in the memo itself.
                        Silently emitting a memo that failed its own
                        traceability check would be the worst thing this
                        pipeline could do.

    Writes no memo text. This node judges; render_citations presents. It runs
    strictly BEFORE rendering so that an out-of-range <<N>> becomes a clean
    reject here instead of an UnresolvedCitationError in the renderer.
    """
    iterations = state["evaluator_iterations"] + 1
    claims = [Claim(**c) for c in state["claims"]]

    # No claims means write_memo_node already short-circuited to a placeholder
    # (see graph.py). There is nothing to trace, and routing to "rewrite"
    # would call write_memo with zero claims, which raises by design.
    if not claims:
        return {
            "evaluator_iterations": iterations,
            "evaluator_decision": "accept",
            "evaluator_feedback": "no claims collected - nothing to trace",
            "evaluator_violations": [],
        }

    memo = MemoDraft(
        bull_case=state["memo_bull"],
        base_case=state["memo_base"],
        bear_case=state["memo_bear"],
    )

    # A dead or unreachable support model must not silently downgrade the check
    # to tier 1 - that would turn an outage into a quiet loss of coverage. It
    # also must not abort the run, since tier 1 is a real check on its own. So:
    # fall back, and say so in the feedback that gets stored on state.
    support_note = ""
    if support_checker is not None:
        try:
            result = evaluate_memo(memo, claims, support_checker=support_checker)
        except SupportCheckError as exc:
            print(f"[evaluate] support check unavailable, tier 1 only: {exc}")
            support_note = (
                "\n\nNOTE: the semantic support check could not run for this "
                f"pass ({exc}). Only deterministic citation checks were "
                "applied, so a misattributed citation could have gone "
                "undetected here."
            )
            result = trace_memo(memo, claims)
    else:
        result = trace_memo(memo, claims)

    print(
        f"[evaluate] pass {iterations}/{EVALUATOR_CAP}: "
        f"{result.sentences_traced}/{result.sentences_checked} sentences traced, "
        f"{len(result.blocking_violations)} blocking, "
        f"{len(result.advisory_violations)} advisory"
    )

    violations = [v.model_dump() for v in result.violations]

    if result.passed:
        # Advisories are for a human to skim, so log a sample rather than all of
        # them - a memo citing many claims can produce dozens of weak_support
        # notes and drown the rest of the run's output. All of them are on state
        # in evaluator_violations regardless.
        advisories = result.advisory_violations
        for v in advisories[:_ADVISORY_LOG_LIMIT]:
            print(f"[evaluate] advisory: [{v.section}] {v.kind}: {v.sentence!r}")
        if len(advisories) > _ADVISORY_LOG_LIMIT:
            print(
                f"[evaluate] ...and {len(advisories) - _ADVISORY_LOG_LIMIT} more "
                "advisory note(s); see evaluator_violations on state"
            )
        return {
            "evaluator_iterations": iterations,
            "evaluator_decision": "accept",
            "evaluator_feedback": support_note.lstrip(),
            "evaluator_violations": violations,
        }

    feedback = format_feedback(result, claims) + support_note

    if iterations >= EVALUATOR_CAP:
        for v in result.blocking_violations:
            print(f"[evaluate] SHIPPED UNTRACED: [{v.section}] {v.sentence!r}")
        return {
            "evaluator_iterations": iterations,
            "evaluator_decision": "accept_capped",
            "evaluator_feedback": feedback,
            "evaluator_violations": violations,
        }

    return {
        "evaluator_iterations": iterations,
        "evaluator_decision": "rewrite",
        "evaluator_feedback": feedback,
        "evaluator_violations": violations,
    }


def make_evaluate_node(support_checker=None):
    """Build the evaluate graph node.

    support_checker=None gives the deterministic tier-1-only node: free, offline,
    reproducible. Pass check_support (or any callable with its signature) to add
    the tier-2 entailment layer. graph.py wires the real pipeline with tier 2 on
    by default; tests use the default to stay offline.
    """

    def _node(state) -> dict:
        return _evaluate_impl(state, support_checker)

    return _node


# Tier-1-only node. Kept as a module-level name because it's what the unit tests
# and any offline caller want; the real graph builds its own via
# make_evaluate_node(check_support).
evaluate = make_evaluate_node()


def route_from_evaluate(state) -> str:
    """Conditional-edge router for the evaluate node.

    Lives here rather than in graph.py (where the other two routers are)
    because it's part of the evaluator's contract - the set of decisions it can
    emit and which of them loop - and because keeping it out of graph.py means
    it can be tested without importing the whole graph module and every
    specialist's API client along with it.

    Both accept and accept_capped proceed to rendering. The difference between
    them is the warning banner render_citations prepends, not the route: once
    the E-03 cap is spent there is nothing to do but ship what we have and say
    so loudly.
    """
    return (
        "write_memo"
        if state["evaluator_decision"] == "rewrite"
        else "render_citations"
    )


def evaluate_stub(state) -> dict:
    """Test-only stub. Always accepts, so use_stubs=True graphs (whose
    write_memo_stub emits a marker-free placeholder) still terminate."""
    return {
        "evaluator_iterations": state["evaluator_iterations"] + 1,
        "evaluator_decision": "accept",
        "evaluator_feedback": "",
        "evaluator_violations": [],
    }
