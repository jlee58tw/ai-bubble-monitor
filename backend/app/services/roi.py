"""Reliability ROI scenario calculator.

Definitions from the project spec (used exactly):

    Effective Task Cost = AI Inference Cost + Tool Cost + Human Review Cost
                          + Expected Rework Cost + Expected Failure Loss
    Effective ROI       = (Baseline Human Cost - Effective Task Cost) / Baseline Human Cost

Modeling assumptions (how the two expected terms are computed; NOT part of the spec):

    p  = agent success probability (task correct after the normal human review)
    s  = rework share: fraction of failed tasks that can be fixed by rework
    Human Review Cost     = review_minutes / 60 * reviewer_hourly_rate        (every task is reviewed)
    Expected Rework Cost  = (1 - p) * s       * rework_cost                   (failure caught & fixed)
    Expected Failure Loss = (1 - p) * (1 - s) * failure_recovery_cost         (failure not fixable by rework;
                                                                               recovery / loss incurred)
Each failed task is either reworked or a loss, never both, so the two terms do not double count.
All per-task values; totals multiply by task volume.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

SPEC_FORMULAS = {
    "effective_task_cost": "AI Inference Cost + Tool Cost + Human Review Cost + Expected Rework Cost + Expected Failure Loss",
    "effective_roi": "(Baseline Human Cost - Effective Task Cost) / Baseline Human Cost",
}
ASSUMPTIONS = {
    "human_review_cost": "review_minutes / 60 x reviewer_hourly_rate (applied to every task)",
    "expected_rework_cost": "(1 - success_probability) x rework_share x rework_cost",
    "expected_failure_loss": "(1 - success_probability) x (1 - rework_share) x failure_recovery_cost",
    "rework_share": "fraction of failed tasks fixable by rework; the rest become failure losses (no double counting)",
    "break_even_success_probability": "p at which Effective Task Cost = Baseline Human Cost (Effective ROI = 0)",
}


@dataclass(frozen=True)
class RoiInputs:
    success_probability: float = 0.6
    review_minutes: float = 15.0
    reviewer_hourly_rate: float = 60.0
    inference_cost: float = 0.5
    tool_cost: float = 0.1
    rework_cost: float = 20.0
    rework_share: float = 0.7
    failure_recovery_cost: float = 40.0
    baseline_human_cost: float = 30.0
    task_volume: float = 1000.0

    def validate(self) -> None:
        for k in ("success_probability", "rework_share"):
            v = getattr(self, k)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{k} must be between 0 and 1")
        for k, v in asdict(self).items():
            if v < 0:
                raise ValueError(f"{k} must be >= 0")


def compute(x: RoiInputs) -> dict:
    x.validate()
    p, s = x.success_probability, x.rework_share
    review = x.review_minutes / 60.0 * x.reviewer_hourly_rate
    rework = (1 - p) * s * x.rework_cost
    failure = (1 - p) * (1 - s) * x.failure_recovery_cost
    etc = x.inference_cost + x.tool_cost + review + rework + failure
    b = x.baseline_human_cost
    roi = (b - etc) / b if b > 0 else None
    # ETC(p) = fixed + (1 - p) * k  ->  break-even p* = 1 - (B - fixed) / k
    fixed = x.inference_cost + x.tool_cost + review
    k = s * x.rework_cost + (1 - s) * x.failure_recovery_cost
    if k > 0:
        be = 1 - (b - fixed) / k
        be_note = "always profitable (even at p=0)" if be <= 0 else "never breaks even (even at p=1)" if be > 1 else None
    else:
        be = None
        be_note = "failure costs are zero: ROI does not depend on p" + ("" if b > fixed else " (and never breaks even)")
    return {
        "inputs": asdict(x),
        "per_task": {"ai_inference_cost": x.inference_cost, "tool_cost": x.tool_cost, "human_review_cost": review,
                     "expected_rework_cost": rework, "expected_failure_loss": failure,
                     "effective_task_cost": etc, "baseline_human_cost": b},
        "effective_roi": roi,
        "totals": {"effective_task_cost": etc * x.task_volume, "baseline_human_cost": b * x.task_volume,
                   "net_savings": (b - etc) * x.task_volume},
        "break_even_success_probability": be,
        "break_even_note": be_note,
        "formulas": SPEC_FORMULAS,
        "assumptions": ASSUMPTIONS,
    }
