"""Renders a SAFContext as a markdown briefing for OpenClaw bootstrapFiles.

The briefing is written to memory/shared/runtime/SAF_BRIEFING.md on every
turn and injected into OpenClaw's system prompt via the bootstrapFiles
mechanism.
"""

from skills.saf_core.lib.context import SAFContext


HEADER = """# SAF Briefing (auto-generated, read-only)

> This file is regenerated on every turn by the SAF framework.
> Do not edit. SAF tracks what the agent has already done today to
> prevent duplicate proactive actions.
"""


def render_briefing(context: SAFContext) -> str:
    """Renders the full SAFContext as a markdown briefing."""
    sections = [
        HEADER,
        _render_temporal(context),
        _render_domains(context),
        _render_already_done(context),
        _render_blocked(context),
        _render_instructions(context),
    ]
    return "\n".join(sections)


def _render_temporal(ctx: SAFContext) -> str:
    t = ctx.temporal
    return (
        "## 1. Temporal Context\n"
        f"- **Local time:** {t.get('day_of_week', '?')} "
        f"{t.get('iso_date', '?')} {t.get('local_time', '?')}\n"
        f"- **Timezone:** {t.get('timezone', '?')}\n"
        f"- **Day phase:** {t.get('day_phase', '?')}\n"
        f"- **Day type:** {t.get('day_type', '?')}\n"
    )


def _render_domains(ctx: SAFContext) -> str:
    if not ctx.candidate_domains:
        return (
            "## 2. Relevant Domains\n"
            "_No specific domains matched this message. "
            "Rely on general conversational context._\n"
        )

    lines = ["## 2. Relevant Domains", ""]
    for domain in ctx.candidate_domains:
        lines.append(f"- **{domain.name}** — `{domain.path}/`")
        for filename in domain.files:
            lines.append(f"  - `{filename}`")
        lines.append(f"  - *Reason: {domain.reason}*")
    lines.append("")
    return "\n".join(lines)


def _render_already_done(ctx: SAFContext) -> str:
    done = ctx.dedup.get("already_done_today", [])
    if not done:
        return "## 3. Already Done Today\n_Nothing yet._\n"
    lines = ["## 3. Already Done Today (do not repeat)"]
    for action_id in done:
        lines.append(f"- `{action_id}`")
    lines.append("")
    return "\n".join(lines)


def _render_blocked(ctx: SAFContext) -> str:
    if not ctx.blocked_actions:
        return "## 4. Blocked Actions\n_None._\n"
    lines = ["## 4. Blocked Actions (do not execute)"]
    for action_id, reason in ctx.blocked_actions.items():
        lines.append(f"- `{action_id}` — reason: {reason}")
    lines.append("")
    return "\n".join(lines)


def _render_instructions(ctx: SAFContext) -> str:
    """Renders the agent instructions from the pipeline's pre-built list.

    The pipeline owns instruction prose; the renderer just formats it.
    This avoids the renderer regenerating prose that would drift from
    the pipeline's output.
    """
    if not ctx.agent_instructions:
        return "## 5. Instructions\n_No specific instructions._\n"
    lines = ["## 5. Instructions"]
    for i, instruction in enumerate(ctx.agent_instructions, start=1):
        lines.append(f"{i}. {instruction}")
    lines.append("")
    return "\n".join(lines)
