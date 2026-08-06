"""
Shared pytest setup.

`backend/nodes/market_intel.py` and `backend/nodes/team_signals.py` construct
their ChatGoogleGenerativeAI client at MODULE level, which validates the API key
on import. Anyone without GOOGLE_API_KEY in .env therefore can't even import
`backend.graph`, and six unit-test files fail at collection - not because the
code under test is broken, but because importing it demands a credential.

Placeholder keys are installed here before any test module is imported (conftest
loads first). The tests that touch the graph all pass use_stubs=True, so no
specialist ever invokes the model and the placeholder is never used for
anything. Live runs still need the real keys - see tests/manual/.

Not fixed by lazy-initialising the clients in those two modules, which would be
the better repair, because they belong to other roles. Worth raising with B/C.
"""

import os

for _key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY"):
    os.environ.setdefault(_key, f"placeholder-for-tests-{_key.lower()}")
