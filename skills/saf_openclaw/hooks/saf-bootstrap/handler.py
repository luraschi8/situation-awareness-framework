"""OpenClaw hook handler for agent:bootstrap.

Writes the initial SAF briefing and registers it with bootstrapFiles.
"""

from skills.saf_openclaw.adapter import OpenClawAdapter


def handler(event):
    """OpenClaw lifecycle hook entry point.

    event is expected to have:
      - event.type == "agent"
      - event.action == "bootstrap"
      - event.context.bootstrapFiles (mutable list)
    """
    if event.type != "agent" or event.action != "bootstrap":
        return

    adapter = OpenClawAdapter()
    context = adapter.on_bootstrap()
    briefing_path = adapter.write_briefing(context)

    # Append the briefing to bootstrap files so it's injected into the prompt
    if hasattr(event.context, "bootstrapFiles"):
        event.context.bootstrapFiles.append(briefing_path)
    elif isinstance(event.context, dict) and "bootstrapFiles" in event.context:
        event.context["bootstrapFiles"].append(briefing_path)
