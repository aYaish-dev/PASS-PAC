from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.proxmark_capabilities import (
    get_capability_registry,
    recipe_capabilities,
)
from app.models.assessment import AssessmentEvent
from app.models.measurement import ExperimentBatch, MeasurementTrial
from app.models.operator_command import OperatorCommand
from app.models.transaction_trace import TransactionTrace
from app.services.assurance_service import CRITERIA, evaluate_card_assurance
from app.services.card_service import list_session_cards
from app.services.session_service import get_session_or_404

ENGINE_VERSION = "guided-evidence-engine-v1.0"

GAP_GUIDANCE: dict[str, dict[str, Any]] = {
    "authentication_strength": {
        "title": "Capture authenticated protocol evidence",
        "category": "protocol-evidence",
        "rationale": (
            "Card-family capability does not prove that authentication is used by the "
            "deployed credential application. Capture an authorized reader transaction "
            "or configuration record before awarding full authentication credit."
        ),
        "expected_evidence": [
            "Recognized authentication exchange",
            "Application or reader configuration confirming authenticated use",
        ],
        "target_workspace": "analysis",
    },
    "key_management": {
        "title": "Verify credential key-management controls",
        "category": "control-evidence",
        "rationale": (
            "Key uniqueness, diversification, rotation, or provisioning governance is "
            "not established by card metadata alone."
        ),
        "expected_evidence": [
            "Authorized key-diversification or provisioning record",
            "Key rotation and custody procedure",
        ],
        "target_workspace": None,
    },
    "clone_replay_resistance": {
        "title": "Collect clone and replay-resistance evidence",
        "category": "protocol-evidence",
        "rationale": (
            "Static metadata cannot establish freshness, replay protection, or secure "
            "transaction integrity. Use a bounded authorized transaction trace."
        ),
        "expected_evidence": [
            "Challenge-response or freshness indicators",
            "Secure-messaging or transaction-integrity evidence",
        ],
        "target_workspace": "analysis",
    },
    "reader_backend_enforcement": {
        "title": "Validate reader and backend enforcement",
        "category": "deployment-evidence",
        "rationale": (
            "Credential observations cannot prove whether the access decision uses only "
            "an identifier, application data, or cryptographic verification."
        ),
        "expected_evidence": [
            "Isolated-reader acceptance result",
            "Authorized reader or controller configuration evidence",
        ],
        "target_workspace": None,
    },
    "lifecycle_monitoring": {
        "title": "Document lifecycle and monitoring controls",
        "category": "operational-evidence",
        "rationale": (
            "Revocation, audit logging, duplicate detection, and credential monitoring "
            "remain unknown until operational evidence is documented."
        ),
        "expected_evidence": [
            "Credential revocation procedure and target time",
            "Audit-log retention and duplicate-identifier response",
        ],
        "target_workspace": None,
    },
}


def build_evidence_guidance(
    db: Session,
    session_id: int,
    policy_id: str = "university-standard",
) -> dict[str, Any]:
    session = get_session_or_404(db, session_id)
    cards = list_session_cards(db, session_id)
    registry = get_capability_registry()
    recipes = {item["key"]: item for item in recipe_capabilities()}
    executed_commands = _executed_commands(db, session_id, cards)
    can_run_recipe = session.mode in {"proxmark", "live"} and session.status == "running"
    blocking_reason = _recipe_blocking_reason(session.mode, session.status)

    recommendations: list[dict[str, Any]] = []
    card_results: list[dict[str, Any]] = []
    gaps_by_criterion: dict[str, list[int]] = defaultdict(list)
    critical_card_ids: list[int] = []

    if not {"hw version", "hw status", "hw tune"}.issubset(executed_commands):
        recommendations.append(
            _recipe_recommendation(
                recommendation_id="device-baseline",
                rank=5,
                priority="now",
                title="Establish the device and antenna baseline",
                rationale=(
                    "Firmware identity, hardware status, and antenna tuning should be "
                    "recorded before interpreting credential measurements."
                ),
                recipe=recipes["device-baseline"],
                card_ids=[],
                can_execute=can_run_recipe,
                blocking_reason=blocking_reason,
            )
        )

    for card in cards:
        assurance = evaluate_card_assurance(db, card.id, policy_id)
        gaps = [
            {
                "criterion_id": item["id"],
                "criterion_name": item["name"],
                "detail": item["summary"],
            }
            for item in assurance["criteria"]
            if item["rating"] is None
        ]
        for gap in gaps:
            gaps_by_criterion[gap["criterion_id"]].append(card.id)
        if assurance["critical_failure"]:
            critical_card_ids.append(card.id)

        recipe_key = _recipe_for_card(card.card_type, card.protocol, card.technology)
        recipe = recipes.get(recipe_key) if recipe_key else None
        if recipe and not set(recipe["commands"]).issubset(
            _card_executed_commands(card, executed_commands)
        ):
            recommendations.append(
                _recipe_recommendation(
                    recommendation_id=f"card-{card.id}-{recipe['key']}",
                    rank=10,
                    priority="now",
                    title=f"Complete the {card.card_type} evidence profile",
                    rationale=(
                        "This credential is missing one or more registered read-only "
                        "identity or family-metadata observations. Place this authorized "
                        "card on the antenna before running the recipe."
                    ),
                    recipe=recipe,
                    card_ids=[card.id],
                    can_execute=can_run_recipe,
                    blocking_reason=blocking_reason,
                )
            )

        card_results.append(
            {
                "card_id": card.id,
                "card_type": card.card_type,
                "technology": card.technology,
                "score": assurance["score"],
                "score_lower_bound": assurance["score_lower_bound"],
                "score_upper_bound": assurance["score_upper_bound"],
                "coverage_percent": assurance["coverage_percent"],
                "policy_status": assurance["policy_status"],
                "critical_failure": assurance["critical_failure"],
                "evidence_gaps": gaps,
            }
        )

    for criterion_id, card_ids in gaps_by_criterion.items():
        guidance = GAP_GUIDANCE[criterion_id]
        target_workspace = guidance["target_workspace"]
        recommendations.append(
            {
                "id": f"gap-{criterion_id}",
                "rank": 20 if criterion_id == "reader_backend_enforcement" else 30,
                "priority": "now" if criterion_id == "reader_backend_enforcement" else "next",
                "category": guidance["category"],
                "scope": f"{len(card_ids)} credential(s)",
                "card_ids": sorted(card_ids),
                "title": guidance["title"],
                "rationale": guidance["rationale"],
                "expected_evidence": guidance["expected_evidence"],
                "safety_tier": "controlled_manual_evidence",
                "action_type": "navigate" if target_workspace else "manual",
                "recipe_key": None,
                "href": None,
                "target_workspace": target_workspace,
                "can_execute": False,
                "blocking_reason": (
                    None if target_workspace else "This step requires authorized operational or laboratory evidence."
                ),
            }
        )

    batches = list(
        db.scalars(
            select(ExperimentBatch)
            .where(ExperimentBatch.session_id == session_id)
            .order_by(ExperimentBatch.id.asc())
        ).all()
    )
    trial_count = db.scalar(
        select(MeasurementTrial.id)
        .where(MeasurementTrial.session_id == session_id)
        .limit(1)
    )
    baseline_batches = [item for item in batches if item.condition == "baseline"]
    post_batches = [item for item in batches if item.condition == "post_remediation"]
    if cards and not baseline_batches:
        recommendations.append(
            _navigation_recommendation(
                "create-baseline",
                15,
                "now",
                "Create the controlled baseline experiment",
                "No baseline batch exists for the observed credentials. Repeated trials are required before remediation claims can be evaluated.",
                ["Controlled distances and repetitions", "Timing and correct-identification rates"],
                f"/sessions/{session_id}/measurements",
                list(card.id for card in cards),
            )
        )
    elif baseline_batches and not post_batches and any(
        item.status == "completed" for item in baseline_batches
    ):
        recommendations.append(
            _navigation_recommendation(
                "create-post-remediation",
                25,
                "next",
                "Prepare a post-remediation comparison batch",
                "The baseline is complete, but no post-remediation batch exists. Apply one documented control and repeat the same conditions.",
                ["Matched post-remediation trials", "Transparent baseline deltas"],
                f"/sessions/{session_id}/measurements",
                list(card.id for card in cards),
            )
        )
    elif baseline_batches and any(item.status == "open" for item in baseline_batches) and trial_count:
        recommendations.append(
            _navigation_recommendation(
                "complete-baseline",
                15,
                "now",
                "Review and complete the open baseline batch",
                "An experiment batch contains trials but remains open, so exports should not yet be treated as final evidence.",
                ["Finalized baseline timestamp", "Locked trial set"],
                f"/sessions/{session_id}/measurements",
                list(card.id for card in cards),
            )
        )

    trace_exists = db.scalar(
        select(TransactionTrace.id)
        .where(TransactionTrace.session_id == session_id)
        .limit(1)
    )
    hf_gap_ids = sorted(
        set(gaps_by_criterion.get("authentication_strength", []))
        | set(gaps_by_criterion.get("clone_replay_resistance", []))
    )
    if hf_gap_ids and trace_exists is None:
        recommendations.append(
            {
                "id": "capture-transaction-trace",
                "rank": 18,
                "priority": "now",
                "category": "protocol-evidence",
                "scope": f"{len(hf_gap_ids)} credential(s)",
                "card_ids": hf_gap_ids,
                "title": "Analyze an authorized reader transaction",
                "rationale": "A passive transaction trace can reduce authentication and replay-resistance uncertainty without modifying the credential.",
                "expected_evidence": ["Normalized frame timeline", "Authentication-state indicators", "Trace-quality limitations"],
                "safety_tier": "passive_analysis",
                "action_type": "navigate",
                "recipe_key": None,
                "href": None,
                "target_workspace": "analysis",
                "can_execute": False,
                "blocking_reason": None,
            }
        )

    if critical_card_ids:
        recommendations.append(
            _navigation_recommendation(
                "critical-path-remediation",
                12,
                "now",
                "Prioritize remediation of critical credential paths",
                "One or more credentials contain an explicit critical indicator. Preserve the baseline before changing keys, readers, or credential technology.",
                ["Documented remediation action", "Repeatable post-remediation evidence"],
                f"/sessions/{session_id}/measurements",
                critical_card_ids,
            )
        )

    if not cards:
        recommendations.extend(
            [
                _recipe_recommendation(
                    recommendation_id="discover-hf",
                    rank=10,
                    priority="now",
                    title="Acquire the first HF credential profile",
                    rationale="No credential evidence exists in this session. Place one authorized HF card on the antenna.",
                    recipe=recipes["hf-identity"],
                    card_ids=[],
                    can_execute=can_run_recipe,
                    blocking_reason=blocking_reason,
                ),
                _recipe_recommendation(
                    recommendation_id="discover-lf",
                    rank=11,
                    priority="now",
                    title="Acquire the first LF credential profile",
                    rationale="No credential evidence exists in this session. Place one authorized LF card on the antenna.",
                    recipe=recipes["lf-identity"],
                    card_ids=[],
                    can_execute=can_run_recipe,
                    blocking_reason=blocking_reason,
                ),
            ]
        )

    recommendations.sort(key=lambda item: (item["rank"], item["id"]))
    average_coverage = (
        round(sum(item["coverage_percent"] for item in card_results) / len(card_results), 1)
        if card_results
        else 0.0
    )
    open_gap_count = sum(len(item["evidence_gaps"]) for item in card_results)
    if not cards:
        overall_status = "acquisition_required"
    elif open_gap_count or critical_card_ids:
        overall_status = "evidence_incomplete"
    else:
        overall_status = "ready_for_policy_review"

    return {
        "engine_version": ENGINE_VERSION,
        "registry_version": registry["version"],
        "generated_at": datetime.now(timezone.utc),
        "session_id": session_id,
        "policy_id": policy_id,
        "overall_status": overall_status,
        "card_count": len(card_results),
        "average_coverage_percent": average_coverage,
        "critical_path_count": len(critical_card_ids),
        "open_gap_count": open_gap_count,
        "executable_recommendation_count": sum(
            item["action_type"] == "recipe" and item["can_execute"]
            for item in recommendations
        ),
        "cards": card_results,
        "recommendations": recommendations,
    }


def _executed_commands(
    db: Session,
    session_id: int,
    cards: list[Any],
) -> set[str]:
    commands = {
        item.command
        for item in db.scalars(
            select(OperatorCommand).where(OperatorCommand.session_id == session_id)
        ).all()
        if item.success
    }
    commands.update(
        item.command
        for item in db.scalars(
            select(AssessmentEvent).where(AssessmentEvent.session_id == session_id)
        ).all()
        if item.command and item.status in {"succeeded", "no_card", "warning"}
    )
    for card in cards:
        commands.update(_card_evidence_commands(card))
    return {" ".join(item.lower().split()) for item in commands if item}


def _card_executed_commands(card: Any, session_commands: set[str]) -> set[str]:
    return session_commands | _card_evidence_commands(card)


def _card_evidence_commands(card: Any) -> set[str]:
    normalized = card.normalized_data_json if isinstance(card.normalized_data_json, dict) else {}
    commands: set[str] = set()
    raw_output = normalized.get("raw_output")
    if isinstance(raw_output, dict) and isinstance(raw_output.get("command"), str):
        commands.add(raw_output["command"])
    inspection = normalized.get("inspection")
    if isinstance(inspection, dict):
        for item in inspection.get("commands", []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                commands.add(item["command"])
    return {" ".join(item.lower().split()) for item in commands}


def _recipe_for_card(card_type: str, protocol: str, technology: str) -> str | None:
    family = f"{card_type} {protocol}".lower()
    if "mifare classic" in family:
        return "hf-mifare-profile"
    if "desfire" in family:
        return "hf-desfire-profile"
    if "ntag" in family or "ultralight" in family:
        return "hf-type2-profile"
    if "15693" in family:
        return "hf-iso15693-profile"
    if "iclass" in family:
        return "hf-iclass-profile"
    if "emv" in family or "payment credential" in family:
        return "hf-emv-profile"
    if "em410" in family or "em 410" in family or "tk410" in family:
        return "lf-em410x-profile"
    if "hid" in family and "prox" in family:
        return "lf-hid-profile"
    if "t55" in family:
        return "lf-t55xx-profile"
    if "lf" in technology.lower():
        return "lf-identity"
    if "14443" in family or "hf" in technology.lower() or "nfc" in technology.lower():
        return "hf-identity"
    return None


def _recipe_recommendation(
    *,
    recommendation_id: str,
    rank: int,
    priority: str,
    title: str,
    rationale: str,
    recipe: dict[str, Any],
    card_ids: list[int],
    can_execute: bool,
    blocking_reason: str | None,
) -> dict[str, Any]:
    return {
        "id": recommendation_id,
        "rank": rank,
        "priority": priority,
        "category": "registered-acquisition",
        "scope": f"{len(card_ids)} credential(s)" if card_ids else "session",
        "card_ids": card_ids,
        "title": title,
        "rationale": rationale,
        "expected_evidence": recipe["expected_evidence"],
        "safety_tier": recipe["safety_tier"],
        "action_type": "recipe",
        "recipe_key": recipe["key"],
        "href": None,
        "target_workspace": None,
        "can_execute": can_execute,
        "blocking_reason": None if can_execute else blocking_reason,
    }


def _navigation_recommendation(
    recommendation_id: str,
    rank: int,
    priority: str,
    title: str,
    rationale: str,
    expected_evidence: list[str],
    href: str,
    card_ids: list[int],
) -> dict[str, Any]:
    return {
        "id": recommendation_id,
        "rank": rank,
        "priority": priority,
        "category": "research-workflow",
        "scope": f"{len(card_ids)} credential(s)" if card_ids else "session",
        "card_ids": sorted(card_ids),
        "title": title,
        "rationale": rationale,
        "expected_evidence": expected_evidence,
        "safety_tier": "controlled_research",
        "action_type": "navigate",
        "recipe_key": None,
        "href": href,
        "target_workspace": None,
        "can_execute": False,
        "blocking_reason": None,
    }


def _recipe_blocking_reason(mode: str, status: str) -> str | None:
    if mode not in {"proxmark", "live"}:
        return "A running Proxmark session is required to execute this recipe."
    if status != "running":
        return "Start the session before executing a registered recipe."
    return None
