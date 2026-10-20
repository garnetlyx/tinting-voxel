"""Server-side backstop for over-budget heavy jobs.

The browser asks the user before submitting an oversized job (via
/api/v2/estimate-job); this guard is the second line of defense for clients
that skip the estimate, refusing the job with a structured 422 that carries
the same suggestion the dialog would have shown. ``forceOversize`` on the
request marks the user's explicit "run it anyway".
"""
import logging

from fastapi import HTTPException

from config.settings import settings
from services.memory_estimate import Reduction
from services.telemetry import emit

logger = logging.getLogger(__name__)

JOB_TOO_LARGE = "job_too_large"


def check_memory_budget(
    kind: str,
    estimated_mb: float,
    suggestion: Reduction | None,
    forced: bool,
) -> None:
    """Emit the estimate verdict and refuse over-budget jobs unless forced.

    The force escape hatch has its own ceiling (settings.heavy_memory_hard_cap_mb):
    a job past it can OOM-kill the container, so it is refused outright. The cap
    binds on its own - an estimate past it is refused even when the budget would
    allow it - so a mis-set budget can never void the ceiling.
    """
    budget_mb = settings.heavy_memory_budget_mb
    hard_cap_mb = settings.heavy_memory_hard_cap_mb
    over = estimated_mb > budget_mb
    unforceable = estimated_mb > hard_cap_mb
    if unforceable:
        verdict = "refused"
    elif not over:
        verdict = "ok"
    elif forced:
        verdict = "forced"
    else:
        verdict = "oversize"
    emit(
        "memory_estimate",
        kind=kind,
        estimated_mb=round(estimated_mb),
        budget_mb=round(budget_mb),
        verdict=verdict,
    )
    if not unforceable and (not over or forced):
        return
    force_allowed = not unforceable
    detail = {
        "code": JOB_TOO_LARGE,
        "estimatedMb": round(estimated_mb),
        "budgetMb": round(budget_mb),
        "forceAllowed": force_allowed,
        "message": (
            f"This job is estimated to need {estimated_mb / 1024:.1f} GB of memory, "
            f"over the {budget_mb / 1024:.1f} GB server budget, and could crash it. "
            "Scale down, or confirm to run it anyway."
        )
        if force_allowed
        else (
            f"This job is estimated to need {estimated_mb / 1024:.1f} GB of memory, "
            f"beyond what this server can run even with explicit confirmation "
            "without crashing it. Scale down to continue."
        ),
    }
    if suggestion is not None:
        detail["suggestion"] = suggestion.as_dict()
    if force_allowed:
        logger.info(
            "Refusing over-budget job: kind=%s estimated=%.0fMB budget=%.0fMB",
            kind, estimated_mb, budget_mb,
        )
    else:
        logger.info(
            "Refusing unforceable job: kind=%s estimated=%.0fMB hard_cap=%.0fMB",
            kind, estimated_mb, hard_cap_mb,
        )
    raise HTTPException(status_code=422, detail=detail)
