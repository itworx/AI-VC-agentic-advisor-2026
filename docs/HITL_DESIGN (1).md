# HITL Design (H-01)

**Owner:** Sara (Role A)
**Related tasks:** H-01, H-02, H-03, H-04

## decision
The HITL pause happens **after screening, before specialists run**. Node is called `human_approval`.

The graph looks like:

```
START → screen → human_approval → supervisor ⟷ specialists → write_memo → render_citations → evaluate → END
                       ↓
                (if human rejects, or screen already rejected)
                       ↓
                      END
```

## Why here and not before screening

1. If the pause is right after the human types the input, they're just confirming their own typing. That's not really a decision, it's a click. People auto-approve those quickly.

2. If the pause is after screening, the human sees the verdict and reason and gets to say "yes, go spend money on specialists" or "no, save the money." That's an actual decision.

3. `interrupt()` is the hardest technical piece in this project. If it's at the very start of the graph and it breaks, nothing runs at all. Putting it after screening means that if HITL is buggy the day before the Day 5 demo, I can still show screening + a specialist working.

## What the human sees when it pauses

When the graph hits `human_approval`, it pauses and shows whoever's running it this payload:

```python
{
    "company_name": state["company_name"],
    "company_url": state["company_url"],
    "screening_decision": state["screening_decision"],   # "pass" or "reject"
    "screening_reason": state["screening_reason"],
    "prompt": "Review the screening decision. Approve to continue, override to reverse, or add focus areas for the specialists."
}
```

So they see the verdict, the reason for it, and a prompt asking what to do.

## What the human can send back

The response comes through `Command(resume=...)` in this shape:

```python
{
    "approved": bool,                    # True = proceed with current decision
    "override_decision": Optional[str],  # "pass" or "reject", reverses screening
    "override_reason": Optional[str],    # required if override_decision is set
    "notes": Optional[str]               # focus areas for specialists, added to context
}
```

Three things they can actually do:

- **Just approve:** `{"approved": True}`. Whatever screening decided, we go with it.
- **Override:** `{"approved": True, "override_decision": "pass", "override_reason": "strategic exception"}`. Flips the screening decision. Written reason required so we can log it.
- **Approve and add focus:** `{"approved": True, "notes": "Focus on their retention numbers, not their headcount"}`. Go with screening's decision but pass extra context to the specialists.

They can also send `{"approved": False}` to end the run entirely. Not the common case but I want to support it.

## State fields this node writes

The fields are already in `backend/state.py`:

- `human_approved: bool`, set from `approved` in the response
- `human_notes: str`, set from `notes` if provided, else `""`

Two fields get updated indirectly if the human overrides:

- `screening_decision` gets overwritten if `override_decision` is set
- `screening_reason` gets the override reason appended to it

The decision log also gets a new entry noting what the human did.

## What happens after human_approval

Conditional edge from the node:

```python
def route_after_human_approval(state: State) -> str:
    if not state["human_approved"]:
        return "END"                          # human said no
    if state["screening_decision"] == "reject":
        return "END"                          # screen said reject and human didn't override
    return "supervisor"                       # go do the research
```

The check on `screening_decision` reads its current value, so if the human overrode reject to pass, we route to supervisor as expected.

## What this changes for the screen node

Nothing. Screen still runs on its own, produces a decision and reason, then hands off. It doesn't need to know a human is coming next, which means I can test screen by itself without any of this.

## What this changes for cost

The whole point of the placement:

- **Screen says reject, human agrees:** screen call + human review. No specialists. Cheap.
- **Screen says pass, human agrees:** screen call + human review + full specialist run. Normal cost.
- **Human overrides to pass:** normal cost, but logged so we can report on override frequency.
- **Human overrides to reject:** screen call + human review. No specialists. Cheap, human made the call.

For I-06 (cost tracking), the reject-vs-full ratio becomes a four-way breakdown instead of two.

