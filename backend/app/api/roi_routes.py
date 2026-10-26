"""Reliability ROI scenario calculator endpoint (pure calculation, no stored data)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services.roi import RoiInputs, compute

router = APIRouter(prefix="/api")
D = RoiInputs()


@router.get("/roi")
def roi(
    success_probability: float = Query(D.success_probability, ge=0, le=1),
    review_minutes: float = Query(D.review_minutes, ge=0),
    reviewer_hourly_rate: float = Query(D.reviewer_hourly_rate, ge=0),
    inference_cost: float = Query(D.inference_cost, ge=0),
    tool_cost: float = Query(D.tool_cost, ge=0),
    rework_cost: float = Query(D.rework_cost, ge=0),
    rework_share: float = Query(D.rework_share, ge=0, le=1),
    failure_recovery_cost: float = Query(D.failure_recovery_cost, ge=0),
    baseline_human_cost: float = Query(D.baseline_human_cost, ge=0),
    task_volume: float = Query(D.task_volume, ge=0),
):
    """Effective Task Cost / Effective ROI per the spec. Scenario only: all inputs are user assumptions."""
    params = dict(locals())
    try:
        return compute(RoiInputs(**params))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
