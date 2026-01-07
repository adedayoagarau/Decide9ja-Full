# Archived Message Handlers

These handlers have been deprecated in favor of `message_handler_v4.py` which is now the primary unified handler.

## Handler Evolution

| Version | File | Status | Notes |
|---------|------|--------|-------|
| v1 | `message_handler_v1.py` | **Archived** | Original basic handler |
| v2 | `message_handler_v2.py` | **Archived** | Google Deepmind conversation design |
| v3 | `message_handler_v3.py` | **Archived** | State-first architecture (merged into v4) |
| v4 | `../message_handler_v4.py` | **Active** | Claude-first + SOT prompts + agentic retrieval |

## What was merged into v4

From v3:
- CONTROVERSIAL_TOPICS list for balanced treatment
- `is_controversial_topic()` function
- State management patterns
- Flow handling (onboarding, issue reporting, clarification, confirmation)

## Why archive instead of delete

- Reference for understanding evolution
- May contain edge case handlers needed later
- Documentation of previous approaches

## Do NOT import from these files

All imports should use `message_handler_v4`:

```python
from app.services.message_handler_v4 import handle_message
```
