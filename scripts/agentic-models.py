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


def legacy_route(task, capabilities, attempts=None, minimum_level=0):
    """Plan a sub-agent override from caller-verified availability, not pricing.

    attempts are scoped by task_id. Capacity escalation requires outcome=FAIL,
    diagnosis_kind=capacity and a nonempty diagnosis. Other failures block retry.
    Unknown usage metrics remain null; cost_rank is supplied relative ordering.
    """
    level = max(classify(task), minimum_level)
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
                level = max(classify(task), minimum_level)
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



ROLES = ("orchestrator", "explorer", "test-author", "implementer", "reviewer", "lead-tech")
SELECTORS = {"role": ROLES, "phase": ("PREPARE", "BUILD", "SHIP"),
             "risk": ("low", "ordinary", "high", "critical", "security_critical")}
MODALITIES = ("text", "image", "audio", "video")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def object_fields(value, allowed, label):
    require(isinstance(value, dict), label + " must be an object")
    require(not set(value) - set(allowed), label + " has unknown fields")


def validate_choice(choice):
    object_fields(choice, ("model", "harness"), "preference")
    require(len(choice) == 1 and all(isinstance(v, str) and v.strip()
                                    for v in choice.values()), "preference requires model or harness")


def validate_policy(policy):
    object_fields(policy, ("version", "enabled", "rules"), "routing_policy")
    require(type(policy.get("version")) is int and policy["version"] == 1,
            "routing_policy version must be 1")
    require(type(policy.get("enabled")) is bool, "routing_policy enabled must be boolean")
    rules = policy.get("rules")
    require(isinstance(rules, list), "routing_policy rules must be a list")
    ids = set()
    for rule in rules:
        object_fields(rule, ("id", "match", "priority", "prefer", "effort", "minimum_level",
                             "fallback"), "rule")
        name = rule.get("id")
        require(isinstance(name, str) and name.strip() and name not in ids,
                "rule requires unique nonempty id")
        ids.add(name)
        match = rule.get("match")
        object_fields(match, SELECTORS, "rule match")
        require(all(isinstance(v, str) and v in SELECTORS[k] for k, v in match.items()),
                "unknown rule selector value")
        require(type(rule.get("priority", 0)) is int, "rule priority must be integer")
        preferences = rule.get("prefer")
        require(isinstance(preferences, list) and preferences, "rule prefer must be nonempty list")
        for choice in preferences:
            validate_choice(choice)
        require(rule.get("fallback", "blocked") in ("blocked", "least_cost"),
                "unknown fallback")
        require(rule.get("minimum_level", "LOW") in LEVELS, "unknown minimum_level")
        require("effort" not in rule or rule["effort"] in EFFORTS, "unsupported rule effort")
    return rules


def policy_context(task, rules):
    for key, allowed in SELECTORS.items():
        value = task.get(key, "ordinary" if key == "risk" else None)
        require(isinstance(value, str) and value in allowed, "unknown or missing task " + key)
    if task["role"] in ("reviewer", "lead-tech"):
        sessions = [task.get("session_id"), task.get("implementer_session_id")]
        require(all(isinstance(s, str) and s.strip() for s in sessions) and
                sessions[0] != sessions[1], "review requires distinct, explicit session identities")
    matching = [r for r in rules if all(task.get(k, "ordinary" if k == "risk" else None) == v
                                      for k, v in r["match"].items())]
    override = task.get("routing_override")
    if "routing_override" in task:
        object_fields(override, ("model", "effort"), "routing_override")
        validate_choice({"model": override.get("model")})
        require("effort" not in override or override["effort"] in EFFORTS,
                "unsupported override effort")
        priority = max((r.get("priority", 0) for r in matching), default=0)
        floor = max((LEVELS.index(r.get("minimum_level", "LOW")) for r in matching
                     if r.get("priority", 0) == priority), default=0)
        return None, {"prefer": [{"model": override["model"]}], "minimum_level": LEVELS[floor],
                      **({"effort": override["effort"]} if "effort" in override else {})}
    if not matching:
        return None, {}
    priority = max(r.get("priority", 0) for r in matching)
    winners = [r for r in matching if r.get("priority", 0) == priority]
    require(len(winners) == 1, "conflicting rules at winning priority")
    return winners[0]["id"], winners[0]


def eligible_inventory(task, capabilities):
    requested = task.get("modalities", ["text"])
    require(isinstance(requested, list) and requested and
            all(isinstance(m, str) and m in MODALITIES for m in requested),
            "task modalities must be an explicit nonempty supported list")
    models = []
    for model in capabilities["models"]:
        for flag in ("available", "enabled"):
            require(type(model.get(flag, True)) is bool, flag + " must be boolean")
        if "harness" in model:
            require(isinstance(model["harness"], str) and model["harness"].strip(),
                    "harness must be a nonempty string")
        modalities = model.get("modalities", ["text"])
        require(isinstance(modalities, list) and modalities and
                all(isinstance(m, str) and m in MODALITIES for m in modalities),
                "inventory modalities must be an explicit supported list")
        if (model.get("available", True) and model.get("enabled", True) and
                set(requested) <= set(modalities)):
            models.append(model)
    return {**capabilities, "models": models}


def route(task, capabilities, attempts=None, policy=None):
    """Advisory only. Optional policy never applies a model or launches a harness."""
    if policy is None:
        return legacy_route(task, capabilities, attempts)
    try:
        rules = validate_policy(policy)
        if not policy["enabled"]:
            return legacy_route(task, capabilities, attempts)
        # Validate the entire inventory/history first, even candidates later excluded.
        legacy_route(task, capabilities, attempts)
        matched, selection = policy_context(task, rules)
        minimum = max(LEVELS.index(selection.get("minimum_level", "LOW")),
                      2 if task["role"] in ("reviewer", "lead-tech") else 0)
        inventory = eligible_inventory(task, capabilities)
        if "effort" in selection:
            inventory = {**inventory, "models": [
                {**m, "efforts": [selection["effort"]] if selection["effort"] in m["efforts"] else []}
                for m in inventory["models"]]}
        result = legacy_route(task, inventory, attempts, minimum)
        trace = {"matched_rule": matched, "source": "override" if "routing_override" in task
                 else "rule" if matched else "legacy", "fallback_used": False,
                 "context": {k: task.get(k, "ordinary") for k in SELECTORS},
                 "attempted_preferences": [], "preference_index": None}
        result.update(policy=trace, observed=None, verification="not_verified")
        for index, choice in enumerate(selection.get("prefer", [])):
            trace["attempted_preferences"].append(dict(choice))
            key, value = next(iter(choice.items()))
            field = "id" if key == "model" else "harness"
            subset = {**inventory, "models": [m for m in inventory["models"] if m.get(field) == value]}
            candidate = legacy_route(task, subset, attempts, minimum)
            if candidate["verdict"] == "PASS":
                trace.update(preference_index=index, fallback_used=index > 0)
                result.update(recommendation=candidate["recommendation"], verdict="PASS",
                              reason="Policy " + trace["source"] + " selected " + str(choice) +
                              (" via ordered fallback" if index else ""))
                return result
        if selection.get("prefer"):
            if selection.get("fallback", "blocked") != "least_cost":
                result.update(verdict="BLOCKED", recommendation=None,
                              reason="No permitted preference supports availability, level, effort and modalities")
            else:
                trace["fallback_used"] = True
                result["reason"] = "Explicit least_cost fallback: " + result["reason"]
        return result
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        return {"verdict": "BLOCKED", "recommendation": None, "applied": False,
                "target": "subagent", "reason": str(error), "observed": None,
                "verification": "not_verified"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON object with task, capabilities, optional attempts")
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.input).read_text())
        result = route(data["task"], data["capabilities"], data.get("attempts", []), data.get("routing_policy"))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        result = {"verdict": "BLOCKED", "applied": False, "reason": str(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
