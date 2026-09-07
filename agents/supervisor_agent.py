"""Supervisor Agent — delegates tasks across the creative crew."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from config.settings import get_settings
from core.errors import StorageError, SupervisorAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_supervisor_crew_path,
)
from schemas.project import ProjectMetadata
from schemas.supervisor import (
    CREW_WORKER_ORDER,
    CrewReport,
    CrewResult,
    DelegationEvent,
    GeminiSupervisorDecision,
    SupervisorDecision,
    TaskBoardItem,
)

logger = get_logger(__name__)

DecideFn = Callable[..., GeminiSupervisorDecision | SupervisorDecision | None]

_ALLOWED = set(CREW_WORKER_ORDER) | {"FINISH"}

_PACK_KEYS: dict[str, str] = {
    "research": "research_report",
    "story": "stories",
    "script": "scripts",
    "director": "director_pack",
    "video_generation": "video_generation_pack",
    "captions": "captions_pack",
    "thumbnail": "thumbnail_pack",
    "seo": "seo_pack",
}


def pack_looks_complete(worker: str, state: dict[str, Any]) -> bool:
    """Heuristic: pack exists and is not an empty/skipped shell."""
    key = _PACK_KEYS.get(worker)
    if not key:
        return False
    pack = state.get(key)
    if not isinstance(pack, dict) or not pack:
        return False
    if pack.get("skipped") is True:
        return False
    if worker == "research":
        return bool(pack.get("claims") or pack.get("summary") or pack.get("topic"))
    if worker in {"story", "script"}:
        items = pack.get("stories") if worker == "story" else pack.get("scripts")
        return bool(items)
    plan = pack.get("plan") if isinstance(pack.get("plan"), dict) else pack
    if isinstance(plan, dict) and plan.get("skipped") is True:
        return False
    return True


class SupervisorAgent(BaseAgent):
    """Decide next crew worker and maintain task board / delegation log."""

    name = "supervisor"

    def __init__(self, decide_fn: DecideFn | None = None) -> None:
        self._decide_fn = decide_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        state: dict[str, Any] | None = None,
        persist: bool = True,
        **_: Any,
    ) -> CrewResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        st = dict(state or {})
        settings = get_settings()
        max_steps = int(settings.supervisor_max_steps)
        max_retries = int(settings.supervisor_max_retries)

        report = self._load_or_init_report(project_id, st)
        crew_step = int(st.get("crew_step") or 0) + 1
        retry_counts = dict(report.retry_counts or st.get("crew_retry_counts") or {})

        if crew_step > max_steps:
            decision = SupervisorDecision(
                next_agent="FINISH",
                task="stop",
                reason=f"Reached SUPERVISOR_MAX_STEPS={max_steps}",
                done=True,
            )
            return self._finalize(
                meta,
                root,
                report,
                decision,
                crew_step,
                retry_counts,
                persist=persist,
                messages=[f"[{self.name}] Max steps reached — FINISH"],
            )

        # Mark pending retries from failed workers
        for item in report.task_board:
            if item.status == "failed":
                attempts = int(retry_counts.get(item.assignee, 0))
                if attempts <= max_retries:
                    item.status = "retry"

        decision = self._decide(st, report, retry_counts, crew_step, max_steps, max_retries)
        if decision.next_agent not in _ALLOWED:
            decision = SupervisorDecision(
                next_agent="FINISH",
                task="stop",
                reason=f"Invalid next_agent {decision.next_agent!r}; forcing FINISH",
                done=True,
            )
        if decision.next_agent == "FINISH":
            decision.done = True

        messages = [
            f"[{self.name} → {decision.next_agent}] task: {decision.task or '(none)'} "
            f"({decision.reason})"
        ]
        return self._finalize(
            meta,
            root,
            report,
            decision,
            crew_step,
            retry_counts,
            persist=persist,
            messages=messages,
        )

    def mark_worker_result(
        self,
        report: CrewReport,
        *,
        worker: str,
        ok: bool,
        notes: str = "",
        retry_counts: dict[str, int] | None = None,
    ) -> CrewReport:
        """Update task board after a worker returns to the supervisor."""
        counts = dict(retry_counts or report.retry_counts)
        board = list(report.task_board)
        active = next(
            (t for t in reversed(board) if t.assignee == worker and t.status in {"running", "retry", "pending"}),
            None,
        )
        if active is None:
            active = TaskBoardItem(
                id=f"task:{len(board)}",
                assignee=worker,
                task=worker,
                status="running",
                attempt=counts.get(worker, 0) + 1,
            )
            board.append(active)
        if ok:
            active.status = "done"
            active.notes = notes or active.notes
        else:
            counts[worker] = int(counts.get(worker, 0)) + 1
            active.status = "failed"
            active.attempt = counts[worker]
            active.notes = notes or "worker failed"
        report.task_board = board
        report.retry_counts = counts
        report.delegation_log.append(
            DelegationEvent(
                from_agent=worker,
                to_agent="supervisor",
                task=active.task,
                reason=("ok" if ok else "failed") + (f": {notes}" if notes else ""),
            )
        )
        return report

    def _decide(
        self,
        state: dict[str, Any],
        report: CrewReport,
        retry_counts: dict[str, int],
        crew_step: int,
        max_steps: int,
        max_retries: int,
    ) -> SupervisorDecision:
        # Prefer explicit retry targets first
        for item in report.task_board:
            if item.status == "retry" and item.assignee in CREW_WORKER_ORDER:
                if int(retry_counts.get(item.assignee, 0)) <= max_retries:
                    return SupervisorDecision(
                        next_agent=item.assignee,
                        task=item.task or f"Retry {item.assignee}",
                        reason=f"Retry after failure (attempt {retry_counts.get(item.assignee, 0)})",
                        done=False,
                    )

        decide = self._decide_fn
        if decide is None:
            try:
                from tools.llm.gemini import decide_next_crew_agent

                decide = decide_next_crew_agent
            except Exception:  # noqa: BLE001
                decide = None

        if decide is not None:
            try:
                gem = decide(
                    pack_status=self._pack_status_block(state),
                    task_board=self._board_block(report),
                    retry_counts=json.dumps(retry_counts),
                    last_messages="\n".join((state.get("messages") or [])[-8:]),
                    crew_step=crew_step,
                    max_steps=max_steps,
                )
                if gem is not None:
                    nxt = str(getattr(gem, "next_agent", "") or "").strip()
                    if nxt in _ALLOWED:
                        return SupervisorDecision(
                            next_agent=nxt,
                            task=str(getattr(gem, "task", "") or ""),
                            reason=str(getattr(gem, "reason", "") or "gemini"),
                            done=bool(getattr(gem, "done", False)) or nxt == "FINISH",
                        )
            except Exception as exc:  # noqa: BLE001
                logger.info("Supervisor Gemini decide skipped: %s", exc)

        return self._heuristic_decision(state, retry_counts, max_retries)

    def _heuristic_decision(
        self,
        state: dict[str, Any],
        retry_counts: dict[str, int],
        max_retries: int,
    ) -> SupervisorDecision:
        for worker in CREW_WORKER_ORDER:
            if pack_looks_complete(worker, state):
                continue
            fails = int(retry_counts.get(worker, 0))
            if fails > max_retries:
                continue
            return SupervisorDecision(
                next_agent=worker,
                task=f"Produce {worker} pack",
                reason=f"Missing or incomplete {worker} pack",
                done=False,
            )
        return SupervisorDecision(
            next_agent="FINISH",
            task="complete",
            reason="All crew packs complete or exhausted retries",
            done=True,
        )

    def _finalize(
        self,
        meta: ProjectMetadata,
        root: Path,
        report: CrewReport,
        decision: SupervisorDecision,
        crew_step: int,
        retry_counts: dict[str, int],
        *,
        persist: bool,
        messages: list[str],
    ) -> CrewResult:
        report.decisions.append(decision)
        report.retry_counts = retry_counts
        if decision.next_agent != "FINISH":
            report.delegation_log.append(
                DelegationEvent(
                    from_agent="supervisor",
                    to_agent=decision.next_agent,
                    task=decision.task,
                    reason=decision.reason,
                )
            )
            report.task_board.append(
                TaskBoardItem(
                    id=f"task:{len(report.task_board)}",
                    assignee=decision.next_agent,
                    task=decision.task,
                    status="running",
                    attempt=int(retry_counts.get(decision.next_agent, 0)) + 1,
                )
            )
        else:
            report.finished = True
            report.notes = decision.reason or report.notes

        path = ""
        if persist:
            path = str(self._write_report(meta.project_id, root, report))

        # Attach crew_step into messages via side channel in to_state_dict caller
        result = CrewResult(
            supervisor_crew=report,
            supervisor_crew_path=path,
            messages=messages,
        )
        # Stash step for graph node via report notes not ideal — return via messages only
        result.messages.append(f"[{self.name}] crew_step={crew_step}")
        return result

    def _load_or_init_report(self, project_id: str, state: dict[str, Any]) -> CrewReport:
        raw = state.get("supervisor_crew")
        if isinstance(raw, dict) and raw.get("project_id"):
            try:
                return CrewReport.model_validate(raw)
            except Exception:  # noqa: BLE001
                pass
        return CrewReport(project_id=project_id)

    def _pack_status_block(self, state: dict[str, Any]) -> str:
        lines = []
        for worker in CREW_WORKER_ORDER:
            ok = pack_looks_complete(worker, state)
            lines.append(f"- {worker}: {'complete' if ok else 'missing'}")
        return "\n".join(lines)

    def _board_block(self, report: CrewReport) -> str:
        if not report.task_board:
            return "(empty)"
        return "\n".join(
            f"- {t.id} {t.assignee} status={t.status} attempt={t.attempt} {t.task}"
            for t in report.task_board[-12:]
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise SupervisorAgentError(f"Invalid project metadata: {exc}") from exc

    def _write_report(self, project_id: str, root: Path, report: CrewReport) -> Path:
        ensure_project_analysis_dir(project_id)
        path = root / "analysis" / "supervisor_crew.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _ = get_supervisor_crew_path(project_id)
            path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write supervisor_crew.json: {path}") from exc
        return path
