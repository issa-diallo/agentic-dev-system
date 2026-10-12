#!/usr/bin/env python3
"""Recommend from a supplied model inventory; never change the main model."""
import argparse
import json
import math
from pathlib import Path

LEVELS = ("LOW", "MEDIUM", "HIGH", "EXTRA_HIGH")
EFFORTS = {"low": 0, "medium": 1, "high": 2, "xhigh": 3}


def classify(task):
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    risk = task.get("risk", "ordinary").lower()
    kind = task.get("type", "implementation").lower()
    complexity = task.get("complexity", "standard").lower()
    if risk not in ("low", "ordinary", "high", "critical", "security_critical"):
        raise ValueError("unknown risk classification")
    if complexity not in ("simple", "low", "standard", "medium", "complex", "high"):
        raise ValueError("unknown complexity classification")
    if risk in ("critical", "security_critical") or kind in (
            "authentication", "authorization", "security", "migration", "database_migration"):
        return 3
    if risk == "high" or complexity in ("complex", "high") or kind in (
            "architecture", "refactoring", "review", "difficult_bug"):
        return 2
    if complexity in ("simple", "low") and kind in (
            "read", "file_search", "documentation", "mechanical") and risk in ("low", "ordinary"):
        return 0
    return 1


def capacity(model):
    if "tiers" in model:
        tiers = model["tiers"]
        if not isinstance(tiers, list) or not tiers or any(t not in LEVELS for t in tiers):
            raise ValueError("model tiers must be explicit supported levels")
        return {LEVELS.index(t) for t in tiers}
    strength = model.get("max_level", model.get("strength"))
    if strength not in LEVELS:
        raise ValueError("model requires tiers or max_level/strength")
    return set(range(LEVELS.index(strength) + 1))


def route(task, capabilities, attempts=None):
    """Plan a sub-agent override from caller-verified availability, not pricing.

    attempts are scoped by task_id. Capacity escalation requires outcome=FAIL,
    diagnosis_kind=capacity and a nonempty diagnosis. Other failures block retry.
    Unknown usage metrics remain null; cost_rank is supplied relative ordering.
    """
    level = classify(task)
    if not isinstance(capabilities, dict) or not isinstance(capabilities.get("models"), list):
        raise ValueError("capabilities requires an explicit models inventory")
    overrides = capabilities.get("runtime_overrides", False)
    if not isinstance(overrides, bool):
        raise ValueError("runtime_overrides must be boolean")
    if attempts is not None and (not isinstance(attempts, list) or
                                 not all(isinstance(a, dict) for a in attempts)):
        raise ValueError("attempts must be a list of observations")
    task_id = task.get("id")
    if attempts and (not isinstance(task_id, str) or not task_id.strip()):
        raise ValueError("task id required to scope attempts")
    relevant = [a for a in (attempts or []) if task_id is not None and a.get("task_id") == task_id]
    escalations, blocked = [], None
    invalid = any(not isinstance(a.get("task_id"), str) or not a["task_id"].strip() or
                  a.get("outcome") not in ("PASS", "FAIL") or
                  a.get("level") not in LEVELS for a in (attempts or []))
    if invalid:
        blocked = "Invalid attempt history: explicit PASS/FAIL and observed level required"
    else:
        for attempt in relevant:
            if attempt["outcome"] == "PASS":
                # A verified correction closes earlier failures, retaining history.
                blocked = None
                level = classify(task)
                continue
            diagnosis = attempt.get("diagnosis")
            if (attempt.get("diagnosis_kind") != "capacity" or
                    not isinstance(diagnosis, str) or not diagnosis.strip()):
                blocked = "Analyze and fix the failure before another model attempt"
                continue
            previous_index = LEVELS.index(attempt["level"])
            if previous_index == 3:
                blocked = "Highest supported routing level failed; handoff required"
                continue
            # A diagnosed subsequent attempt does not erase an unresolved failure.
            level = max(level, previous_index + 1)
            escalations.append(diagnosis)
    candidates, identifiers = [], set()
    for model in capabilities["models"]:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"].strip():
            raise ValueError("model id required")
        if model["id"] in identifiers:
            raise ValueError("duplicate model id")
        identifiers.add(model["id"])
        tiers = capacity(model)
        efforts = model.get("efforts")
        rank = model.get("cost_rank")
        if (not isinstance(rank, (float, int)) or isinstance(rank, bool) or
                not math.isfinite(rank) or rank < 0):
            raise ValueError("nonnegative finite cost_rank required")
        if not isinstance(efforts, list) or not all(isinstance(e, str) for e in efforts):
            raise ValueError("model efforts list required")
        supported = [e for e in efforts if e in EFFORTS and EFFORTS[e] >= level]
        if level in tiers and supported:
            effort = min(supported, key=lambda e: (EFFORTS[e], e))
            candidates.append((rank, max(tiers), model["id"], effort))
    selected = min(candidates) if candidates and blocked is None else None
    recommendation = {"model": selected[2], "effort": selected[3]} if selected else None
    return {"level": LEVELS[level], "verdict": "PASS" if selected else "BLOCKED",
            "recommendation": recommendation, "applied": False,
            "override_available": overrides, "target": "subagent",
            "reason": blocked or ("Least cost_rank capable model in supplied inventory" if selected
                                  else "No available model and effort support the required level"),
            "escalations": escalations,
            "attempt_history": [dict(a) for a in relevant],
            "metrics": {"tokens": None, "api_cost": None, "codex_quota": None,
                        "duration_seconds": None, "attempts": len(relevant)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON object with task, capabilities, optional attempts")
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.input).read_text())
        result = route(data["task"], data["capabilities"], data.get("attempts", []))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        result = {"verdict": "BLOCKED", "applied": False, "reason": str(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
