---
name: saf-post-message
description: >
  Parses <saf-action id="..." status="..."/> tags from the agent's response
  and records them to the SAF ledger. Fires on message:pre-send, before the
  response reaches the user.
event: message:pre-send
handler: handler.py
---

# saf-post-message

Fires on `message:pre-send`, after the LLM has generated a response but
before it's sent to the user.

Parses the response for action markers of the form:

```
<saf-action id="morning_briefing" status="sent"/>
```

For each tag, calls `pipeline.record_action(action_id, status, host)` which
writes an entry to `collective-ledger.json`. On the next turn, the
`saf-pre-message` hook will read this ledger and the dedup logic will
block the same action from being re-executed.

This hook never modifies the response text. It only observes and logs.
