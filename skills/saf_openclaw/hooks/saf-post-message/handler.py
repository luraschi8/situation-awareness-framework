"""OpenClaw hook handler for message:pre-send.

Parses action tags from the agent's response and records them to the ledger.
"""

from skills.saf_openclaw.adapter import OpenClawAdapter


def handler(event):
    """OpenClaw lifecycle hook entry point.

    event is expected to have:
      - event.type == "message"
      - event.action == "pre-send"
      - event.context.content (the agent's response text)
    """
    if event.type != "message" or event.action != "pre-send":
        return

    response = _extract_response(event)
    if not response:
        return

    adapter = OpenClawAdapter()
    adapter.on_post_message(response)


def _extract_response(event):
    ctx = event.context
    if hasattr(ctx, "content"):
        return ctx.content
    if isinstance(ctx, dict):
        return ctx.get("content")
    return None
