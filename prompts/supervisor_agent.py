"""Prompt templates for the Supervisor Agent."""

from __future__ import annotations

SUPERVISOR_AGENT_SYSTEM = """You are the supervisor of a multi-agent video production crew.

Workers (use these exact ids only):
- research
- story
- script
- director
- video_generation
- captions
- thumbnail
- seo
- FINISH

Pick the single next worker that should run, or FINISH when the crew has produced
the needed creative packs. Prefer the standard order when packs are missing:
research → story → script → director → video_generation → captions → thumbnail → seo → FINISH.

Rules:
- Do NOT invent worker ids.
- Prefer retrying a failed worker only when attempts remain.
- Set done=true only when next_agent is FINISH.
"""


def build_supervisor_user_prompt(
    *,
    pack_status: str,
    task_board: str,
    retry_counts: str,
    last_messages: str,
    crew_step: int,
    max_steps: int,
) -> str:
    return (
        f"Crew step: {crew_step}/{max_steps}\n\n"
        f"Pack status:\n{pack_status or '(none)'}\n\n"
        f"Task board:\n{task_board or '(empty)'}\n\n"
        f"Retry counts:\n{retry_counts or '(none)'}\n\n"
        f"Recent messages:\n{last_messages or '(none)'}\n\n"
        "Return next_agent, task, reason, and done."
    )
