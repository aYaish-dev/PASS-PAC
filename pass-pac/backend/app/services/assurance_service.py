from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detected_card import DetectedCard
from app.models.assurance_evidence import CardAssuranceEvidence
from app.models.finding import Finding
from app.services.analysis_service import build_analysis_context
from app.services.card_service import get_card_or_404, list_session_cards
from app.services.credential_intelligence import build_card_intelligence
from app.services.session_service import get_session_or_404

ENGINE_VERSION = "assurance-engine-v2.1"
METHODOLOGY_VERSION = "access-path-score-v2.1"
SCALE_MAX = 10
CRITERION_MAX = 2
GRADE_MINIMUM_COVERAGE = 80

CRITERIA: dict[str, dict[str, Any]] = {
    "authentication_strength": {
        "name": "Authentication strength",
        "description": "Rates the authentication mechanism demonstrated by the credential path.",
        "levels": {
            "0": "No cryptographic authentication or a static identifier only.",
            "1": "Legacy, weak, or capability-only authentication.",
            "2": "Observed modern mutual or cryptographic authentication.",
            "unknown": "The authentication mechanism is not established by the available evidence.",
        },
    },
    "key_management": {
        "name": "Key management",
        "description": "Rates observed key uniqueness, diversification, rotation, and governance.",
        "levels": {
            "0": "No keys, default keys, or known shared transport keys.",
            "1": "Custom but shared or incompletely governed keys.",
            "2": "Verified diversified keys with managed lifecycle evidence.",
            "unknown": "Key configuration is not established by the available evidence.",
        },
    },
    "clone_replay_resistance": {
        "name": "Clone and replay resistance",
        "description": "Rates resistance to static duplication and replay using observed protocol evidence.",
        "levels": {
            "0": "A static, UID-modifiable, or directly replayable identifier is observed.",
            "1": "Some resistance exists, but legacy weaknesses or incomplete freshness evidence remain.",
            "2": "Challenge-response, freshness, secure messaging, or transaction integrity is observed.",
            "unknown": "Clone and replay resistance is not established by the available evidence.",
        },
    },
    "reader_backend_enforcement": {
        "name": "Reader and backend enforcement",
        "description": "Rates whether the reader and backend enforce more than a presented identifier.",
        "levels": {
            "0": "UID-only authorization is verified.",
            "1": "Partial application or backend validation is verified.",
            "2": "Cryptographic reader enforcement and backend binding are verified.",
            "unknown": "Reader authorization behavior is not established by the available evidence.",
        },
    },
    "lifecycle_monitoring": {
        "name": "Lifecycle and monitoring",
        "description": "Rates revocation, audit logging, duplicate detection, and credential monitoring.",
        "levels": {
            "0": "No revocation, logging, or duplicate monitoring is verified.",
            "1": "Partial or manual lifecycle controls are verified.",
            "2": "Revocation, audit logging, and credential anomaly monitoring are verified.",
            "unknown": "Lifecycle and monitoring controls are not established by the available evidence.",
        },
    },
}

POLICIES: dict[str, dict[str, Any]] = {
    "university-standard": {
        "id": "university-standard",
        "name": "University Standard",
        "version": "2.0",
        "description": "Baseline acceptance profile for normal university buildings, laboratories, and staff areas.",
        "use_case": "General campus physical access",
        "strictness": "balanced",
        "minimum_score": 6.0,
        "minimum_coverage_percent": 80,
        "reject_critical_failures": True,
    },
    "restricted-area": {
        "id": "restricted-area",
        "name": "Restricted Area",
        "version": "2.0",
        "description": "High-assurance profile for data rooms, controlled research, and other restricted spaces.",
        "use_case": "High-assurance and restricted access zones",
        "strictness": "strict",
        "minimum_score": 8.0,
        "minimum_coverage_percent": 100,
        "reject_critical_failures": True,
    },
    "legacy-transition": {
        "id": "legacy-transition",
        "name": "Legacy Transition",
        "version": "2.0",
        "description": "Migration profile for documenting legacy credentials while replacement controls are planned.",
        "use_case": "Legacy inventory and phased credential migration",
        "strictness": "transitional",
        "minimum_score": 4.0,
        "minimum_coverage_percent": 60,
        "reject_critical_failures": True,
    },
}


def list_assurance_policies() -> list[dict[str, Any]]:
    return [_public_policy(policy) for policy in POLICIES.values()]


def get_assurance_policy(policy_id: str) -> dict[str, Any]:
    policy = POLICIES.get(policy_id)
    if policy is None:
        available = ", ".join(POLICIES)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance policy '{policy_id}' was not found. Available policies: {available}.",
        )
    return policy


def evaluate_card_assurance(
    db: Session,
    card_id: int,
    policy_id: str = "university-standard",
) -> dict[str, Any]:
    card = get_card_or_404(db, card_id)
    policy = get_assurance_policy(policy_id)
    context = build_analysis_context(card)
    intelligence = build_card_intelligence(db, card.id)
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.card_id == card.id)
            .order_by(Finding.created_at.asc(), Finding.id.asc())
        ).all()
    )
    operator_evidence = db.scalar(
        select(CardAssuranceEvidence).where(CardAssuranceEvidence.card_id == card.id)
    )

    evaluators = {
        "authentication_strength": _evaluate_authentication_strength,
        "key_management": _evaluate_key_management,
        "clone_replay_resistance": _evaluate_clone_replay_resistance,
        "reader_backend_enforcement": _evaluate_reader_backend_enforcement,
        "lifecycle_monitoring": _evaluate_lifecycle_monitoring,
    }
    results: list[dict[str, Any]] = []
    for criterion_id, evaluator in evaluators.items():
        evaluation = evaluator(
            card=card,
            context=context,
            intelligence=intelligence,
            operator_evidence=operator_evidence,
        )
        rating = evaluation["rating"]
        results.append(
            {
                "id": criterion_id,
                "name": CRITERIA[criterion_id]["name"],
                "outcome": _outcome_for_rating(rating),
                "rating": rating,
                "max_points": CRITERION_MAX,
                **{key: value for key, value in evaluation.items() if key != "rating"},
            }
        )

    known_ratings = [
        int(result["rating"]) for result in results if result["rating"] is not None
    ]
    known_count = len(known_ratings)
    known_sum = sum(known_ratings)
    unknown_count = len(results) - known_count
    score = round(5 * known_sum / known_count, 1) if known_count else None
    lower_bound = known_sum
    upper_bound = known_sum + CRITERION_MAX * unknown_count
    coverage = known_count * 20
    credential_results = results[:3]
    credential_known_ratings = [
        int(result["rating"])
        for result in credential_results
        if result["rating"] is not None
    ]
    credential_known_count = len(credential_known_ratings)
    credential_score = (
        round(5 * sum(credential_known_ratings) / credential_known_count, 1)
        if credential_known_count
        else None
    )
    credential_coverage = round(100 * credential_known_count / len(credential_results))
    credential_grade, credential_grade_label = _credential_grade(
        credential_score,
        credential_coverage,
    )
    critical_failure = any(result["critical"] for result in results)
    confidence = _confidence(coverage, context, operator_evidence)
    grade, grade_label = _grade(score, coverage)
    policy_status, meets_policy = _evaluate_policy_status(
        score=score,
        coverage=coverage,
        critical_failure=critical_failure,
        policy=policy,
    )
    review = _analyst_review_summary(findings)
    recommendations = _deduplicate(
        recommendation
        for result in results
        for recommendation in result["recommendations"]
    )[:8]

    return {
        "engine_version": ENGINE_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "evaluated_at": datetime.now(timezone.utc),
        "policy": _public_policy(policy),
        "card_id": card.id,
        "credential_score": credential_score,
        "credential_coverage_percent": credential_coverage,
        "credential_grade": credential_grade,
        "credential_grade_label": credential_grade_label,
        "score": score,
        "scale_max": SCALE_MAX,
        "score_lower_bound": lower_bound,
        "score_upper_bound": upper_bound,
        "unknown_criteria_count": unknown_count,
        "grade": grade,
        "grade_label": grade_label,
        "coverage_percent": coverage,
        "confidence": confidence,
        "policy_status": policy_status,
        "meets_policy": meets_policy,
        "critical_failure": critical_failure,
        "summary": _score_summary(
            score=score,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            coverage=coverage,
            policy_status=policy_status,
            critical_failure=critical_failure,
        ),
        "criteria": results,
        "recommendations": recommendations,
        "analyst_review": review,
        "evidence_snapshot": {
            "uid": card.uid,
            "card_type": card.card_type,
            "technology": card.technology,
            "protocol": card.protocol,
            "finding_count": len(findings),
            "active_finding_count": review["active_finding_count"],
            "observation_count": intelligence["observation_count"],
            "session_count": intelligence["session_count"],
            "source": context.get("source") or "unknown",
            "operator_evidence_id": operator_evidence.id if operator_evidence else None,
            "operator_evidence_source": (
                operator_evidence.evidence_source if operator_evidence else None
            ),
            "operator_evidence_assessed_at": (
                operator_evidence.assessed_at if operator_evidence else None
            ),
        },
    }


def evaluate_session_assurance(
    db: Session,
    session_id: int,
    policy_id: str = "university-standard",
) -> dict[str, Any]:
    get_session_or_404(db, session_id)
    policy = get_assurance_policy(policy_id)
    cards = list_session_cards(db, session_id)
    evaluations = [evaluate_card_assurance(db, card.id, policy_id) for card in cards]
    summaries = [
        {
            "card_id": card.id,
            "uid": card.uid,
            "card_type": card.card_type,
            "credential_score": evaluation["credential_score"],
            "credential_coverage_percent": evaluation["credential_coverage_percent"],
            "credential_grade": evaluation["credential_grade"],
            "credential_grade_label": evaluation["credential_grade_label"],
            "score": evaluation["score"],
            "score_lower_bound": evaluation["score_lower_bound"],
            "score_upper_bound": evaluation["score_upper_bound"],
            "grade": evaluation["grade"],
            "grade_label": evaluation["grade_label"],
            "coverage_percent": evaluation["coverage_percent"],
            "confidence": evaluation["confidence"],
            "policy_status": evaluation["policy_status"],
            "critical_failure": evaluation["critical_failure"],
        }
        for card, evaluation in zip(cards, evaluations, strict=True)
    ]
    scores = [
        float(evaluation["score"])
        for evaluation in evaluations
        if evaluation["score"] is not None
    ]
    grade_counts = {
        grade: 0 for grade in ("strong", "moderate", "limited", "weak", "inconclusive")
    }
    policy_status_counts = {
        item: 0 for item in ("pass", "fail", "insufficient_evidence")
    }
    for evaluation in evaluations:
        grade_counts[evaluation["grade"]] += 1
        policy_status_counts[evaluation["policy_status"]] += 1

    critical_count = sum(evaluation["critical_failure"] for evaluation in evaluations)
    insufficient_count = policy_status_counts["insufficient_evidence"]
    average_score = round(sum(scores) / len(scores), 1) if scores else None
    lowest_score = min(scores) if scores else None

    if not evaluations:
        summary = (
            "No credentials have been captured in this session, so an access-path "
            "security posture cannot be calculated."
        )
    else:
        summary = (
            f"{len(evaluations)} credential(s) evaluated under {policy['name']} v{policy['version']}; "
            f"{policy_status_counts['pass']} pass, {policy_status_counts['fail']} fail, and "
            f"{insufficient_count} have insufficient evidence. Scores use the same v2 rubric "
            "across all policy profiles."
        )

    return {
        "engine_version": ENGINE_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "evaluated_at": datetime.now(timezone.utc),
        "policy": _public_policy(policy),
        "session_id": session_id,
        "card_count": len(cards),
        "average_score": average_score,
        "lowest_score": lowest_score,
        "critical_failure_count": critical_count,
        "insufficient_evidence_count": insufficient_count,
        "grade_counts": grade_counts,
        "policy_status_counts": policy_status_counts,
        "summary": summary,
        "cards": sorted(
            summaries,
            key=lambda item: (
                item["score"] is not None,
                item["score"] if item["score"] is not None else -1,
                item["card_id"],
            ),
        ),
    }


def _evaluate_authentication_strength(**data: Any) -> dict[str, Any]:
    card: DetectedCard = data["card"]
    context = data["context"]
    fields = _security_fields(card)
    family = f"{card.card_type} / {card.protocol}"

    if (
        context["is_configurable_lf"]
        or context["is_hid_prox"]
        or context["is_basic_lf_identifier"]
    ):
        return _result(
            0,
            True,
            "The observed LF path presents an identifier without cryptographic card authentication.",
            [f"Observed family: {family}"],
            ["Migrate the path to a credential and reader configuration with mutual cryptographic authentication."],
        )
    if _has_verified_crypto_evidence(fields):
        return _result(
            2,
            False,
            "Normalized evidence reports verified cryptographic or mutual authentication.",
            _matched_field_evidence(
                fields,
                "authentication",
                "mutual_authentication",
                "secure_messaging",
            ),
            [],
        )
    if context["is_mifare_classic"]:
        nonce = context.get("nonce_type") or "not established"
        return _result(
            1,
            False,
            "MIFARE Classic provides legacy Crypto1 authentication, but it is not a modern assurance mechanism.",
            [f"Observed family: {family}", f"Nonce classification: {nonce}"],
            ["Plan migration to a modern mutually authenticated credential application."],
        )
    if _is_modern_family(card):
        return _result(
            1,
            False,
            "The credential family is authentication-capable, but use of that capability has not been verified.",
            [f"Capability-level family evidence: {family}"],
            ["Capture an authorized authenticated transaction or configuration record before awarding full credit."],
        )
    if context["is_nfc_tag"]:
        return _result(
            0,
            False,
            "The observed general-purpose NFC tag evidence does not demonstrate cryptographic access authentication.",
            [f"Observed family: {family}"],
            ["Verify that this tag is not used as a static access credential."],
        )
    return _result(
        None,
        False,
        "The authentication mechanism is not established by the available evidence.",
        [],
        ["Collect family-specific metadata or an authorized transaction trace."],
    )


def _evaluate_key_management(**data: Any) -> dict[str, Any]:
    card: DetectedCard = data["card"]
    context = data["context"]
    fields = _security_fields(card)
    value = _first_text(
        fields,
        "key_management",
        "key_diversification",
        "key_strategy",
        "key_scope",
    )
    default_count = _first_int(fields, "default_key_count", "default_keys_found")
    default_keys = fields.get("default_keys")

    if (
        context["is_configurable_lf"]
        or context["is_hid_prox"]
        or context["is_basic_lf_identifier"]
    ):
        return _result(
            0,
            True,
            "The observed LF identifier path has no cryptographic key management layer.",
            [f"Observed family: {card.card_type}"],
            ["Replace static identifier credentials or require a separate authenticated factor."],
        )
    if default_count > 0 or _nonempty_collection(default_keys) or _contains_any(
        value, "default", "factory", "transport"
    ):
        evidence = _matched_field_evidence(
            fields,
            "default_key_count",
            "default_keys_found",
            "default_keys",
            "key_management",
        )
        return _result(
            0,
            True,
            "Default or transport-key evidence is present.",
            evidence,
            ["Replace default keys and verify per-credential diversification on controlled test media."],
        )
    if _contains_any(value, "diversified", "per-card", "per card", "unique", "rotated"):
        return _result(
            2,
            False,
            "Evidence reports diversified or individually managed credential keys.",
            _matched_field_evidence(
                fields,
                "key_management",
                "key_diversification",
                "key_strategy",
                "key_scope",
            ),
            [],
        )
    if _contains_any(value, "custom", "shared", "site", "static"):
        return _result(
            1,
            False,
            "Custom keying is reported, but diversification or lifecycle governance is incomplete.",
            _matched_field_evidence(
                fields,
                "key_management",
                "key_diversification",
                "key_strategy",
                "key_scope",
            ),
            ["Verify per-card diversification, protected provisioning, and rotation procedures."],
        )
    return _result(
        None,
        False,
        "The available evidence does not establish whether keys are default, shared, or diversified.",
        [],
        ["Collect an authorized key-management configuration record without exporting secret key material."],
    )


def _evaluate_clone_replay_resistance(**data: Any) -> dict[str, Any]:
    card: DetectedCard = data["card"]
    context = data["context"]
    intelligence = data["intelligence"]
    fields = _security_fields(card)
    protection = _first_text(
        fields,
        "replay_protection",
        "freshness",
        "transaction_integrity",
        "transaction_mac",
        "secure_messaging",
    )

    if context["magic_card_indicator"] or intelligence["inconsistent_identity"]:
        evidence = []
        if context["magic_card_indicator"]:
            evidence.append("UID-modifiable credential indicator observed")
        if intelligence["inconsistent_identity"]:
            evidence.append("Conflicting metadata is stored for the same normalized UID")
        return _result(
            0,
            True,
            "Identifier integrity evidence indicates direct duplication risk or conflicting identity.",
            evidence,
            ["Verify that the reader rejects UID-only authorization and investigate conflicting observations."],
        )
    if (
        context["non_unique_uid"]
        or context["is_configurable_lf"]
        or context["is_hid_prox"]
        or context["is_basic_lf_identifier"]
    ):
        return _result(
            0,
            True,
            "The observed path relies on a static, configurable, or non-unique identifier.",
            [f"Observed family: {card.card_type}", f"UID: {card.uid}"],
            ["Use challenge-response authentication and monitor duplicate credential identifiers."],
        )
    if _contains_any(
        protection,
        "verified",
        "enabled",
        "challenge-response",
        "challenge response",
        "transaction mac",
        "fresh",
    ):
        return _result(
            2,
            False,
            "Freshness, secure messaging, or transaction-integrity evidence is present.",
            _matched_field_evidence(
                fields,
                "replay_protection",
                "freshness",
                "transaction_integrity",
                "transaction_mac",
                "secure_messaging",
            ),
            [],
        )
    if context["nonce_type"] in {"static", "weak_prng"}:
        return _result(
            0,
            True,
            "Weak or static nonce behavior materially reduces clone and replay resistance.",
            [f"Nonce classification: {context['nonce_type']}"],
            ["Migrate the credential family or validate a formally approved compensating control."],
        )
    if context["is_mifare_classic"]:
        return _result(
            1,
            False,
            "Legacy MIFARE authentication provides limited resistance, with no verified modern freshness control.",
            [f"Observed family: {card.card_type}"],
            ["Validate nonce behavior and migrate to modern secure messaging."],
        )
    if _is_modern_family(card) and _has_verified_crypto_evidence(fields):
        return _result(
            2,
            False,
            "Modern authenticated protocol evidence supports challenge-response resistance.",
            [f"Observed family: {card.card_type}"],
            [],
        )
    if _is_modern_family(card):
        return _result(
            1,
            False,
            "The family can support clone resistance, but freshness and reader use are not verified.",
            [f"Capability-level family evidence: {card.card_type}"],
            ["Capture secure-messaging or challenge-response evidence."],
        )
    return _result(
        None,
        False,
        "Clone and replay resistance is not established by the available evidence.",
        [],
        ["Collect bounded transaction evidence and reader configuration data."],
    )


def _evaluate_reader_backend_enforcement(**data: Any) -> dict[str, Any]:
    card: DetectedCard = data["card"]
    operator_evidence: CardAssuranceEvidence | None = data["operator_evidence"]
    fields = _security_fields(card)
    uid_only = fields.get("uid_only_authorization")
    enforcement = _first_text(
        fields,
        "reader_enforcement",
        "authorization_basis",
        "backend_binding",
        "reader_validation",
    )
    trust_hypothesis = _first_text(fields, "trust_hypothesis")
    authentication_state = _first_text(fields, "authentication_state")

    if operator_evidence and operator_evidence.reader_enforcement:
        state = operator_evidence.reader_enforcement
        evidence = _operator_evidence_details(operator_evidence)
        if state == "uid_only":
            return _result(
                0,
                True,
                "Operator evidence verifies that the access decision relies on a UID or static identifier.",
                evidence,
                ["Require cryptographic credential validation before granting access."],
            )
        if state == "partial":
            return _result(
                1,
                False,
                "Operator evidence verifies partial reader or backend validation.",
                evidence,
                ["Validate the complete reader-to-controller authorization path."],
            )
        if state == "cryptographic":
            return _result(
                2,
                False,
                "Operator evidence verifies cryptographic reader enforcement and backend binding.",
                evidence,
                [],
            )

    if _is_true(uid_only) or _contains_any(
        enforcement, "uid-only", "uid only", "static uid", "identifier only"
    ):
        return _result(
            0,
            True,
            "Authorized evidence reports UID-only reader or backend authorization.",
            _matched_field_evidence(
                fields,
                "uid_only_authorization",
                "reader_enforcement",
                "authorization_basis",
            ),
            ["Require cryptographic credential validation before granting access."],
        )
    if _contains_any(
        enforcement,
        "cryptographic",
        "mutual authentication",
        "backend bound",
        "backend-bound",
        "verified",
    ):
        return _result(
            2,
            False,
            "Reader-side cryptographic enforcement and backend binding are verified.",
            _matched_field_evidence(
                fields,
                "reader_enforcement",
                "authorization_basis",
                "backend_binding",
                "reader_validation",
            ),
            [],
        )
    if _contains_any(
        enforcement,
        "partial",
        "application data",
        "backend lookup",
        "facility code",
    ) or authentication_state == "observed":
        return _result(
            1,
            False,
            "Some reader or backend validation is observed, but the complete access decision is not verified.",
            _matched_field_evidence(
                fields,
                "reader_enforcement",
                "authorization_basis",
                "backend_binding",
                "authentication_state",
            ),
            ["Validate the complete reader-to-controller authorization path."],
        )
    if trust_hypothesis == "uid_only_candidate":
        return _result(
            None,
            False,
            "A trace suggests a UID-only candidate, but passive evidence cannot prove the controller decision.",
            ["Trace trust hypothesis: uid_only_candidate"],
            ["Capture a complete authorized transaction and verify controller configuration."],
        )
    return _result(
        None,
        False,
        "Reader and backend authorization behavior is not established by card metadata alone.",
        [],
        ["Collect authorized reader configuration or isolated-reader acceptance evidence."],
    )


def _evaluate_lifecycle_monitoring(**data: Any) -> dict[str, Any]:
    card: DetectedCard = data["card"]
    operator_evidence: CardAssuranceEvidence | None = data["operator_evidence"]
    fields = _security_fields(card)
    lifecycle = _first_text(
        fields,
        "lifecycle_controls",
        "credential_lifecycle",
        "monitoring_posture",
    )
    control_names = (
        "revocation_enabled",
        "audit_logging",
        "duplicate_detection",
        "credential_monitoring",
    )
    explicit_controls = [
        (name, fields[name]) for name in control_names if name in fields
    ]
    enabled_controls = [name for name, value in explicit_controls if _is_true(value)]

    if operator_evidence and operator_evidence.lifecycle_monitoring:
        state = operator_evidence.lifecycle_monitoring
        evidence = _operator_evidence_details(operator_evidence)
        if state == "absent":
            return _result(
                0,
                False,
                "Operator evidence reports no verified revocation, audit, or duplicate-monitoring controls.",
                evidence,
                ["Implement credential revocation, audit logging, and duplicate monitoring."],
            )
        if state == "partial":
            return _result(
                1,
                False,
                "Operator evidence verifies partial or manual lifecycle controls.",
                evidence,
                ["Document revocation time, audit retention, and duplicate-identifier response."],
            )
        if state == "managed":
            return _result(
                2,
                False,
                "Operator evidence verifies managed revocation, audit, and credential monitoring controls.",
                evidence,
                [],
            )

    if _contains_any(lifecycle, "verified", "managed", "automated") or len(enabled_controls) >= 3:
        return _result(
            2,
            False,
            "Revocation, logging, and anomaly-monitoring controls are verified.",
            _matched_field_evidence(
                fields,
                "lifecycle_controls",
                "credential_lifecycle",
                *control_names,
            ),
            [],
        )
    if _contains_any(lifecycle, "partial", "manual", "limited") or enabled_controls:
        return _result(
            1,
            False,
            "Some lifecycle controls are present, but coverage is partial or manual.",
            _matched_field_evidence(
                fields,
                "lifecycle_controls",
                "credential_lifecycle",
                *control_names,
            ),
            ["Document revocation time, audit retention, and duplicate-identifier response."],
        )
    if explicit_controls and all(_is_false(value) for _, value in explicit_controls):
        return _result(
            0,
            False,
            "Available configuration evidence explicitly reports no lifecycle controls.",
            _matched_field_evidence(fields, *control_names),
            ["Implement credential revocation, audit logging, and duplicate monitoring."],
        )
    if _contains_any(lifecycle, "none", "absent", "disabled"):
        return _result(
            0,
            False,
            "Lifecycle and monitoring controls are explicitly absent or disabled.",
            _matched_field_evidence(
                fields,
                "lifecycle_controls",
                "credential_lifecycle",
                "monitoring_posture",
            ),
            ["Implement credential revocation, audit logging, and duplicate monitoring."],
        )
    return _result(
        None,
        False,
        "Lifecycle and monitoring controls are not established by the available evidence.",
        [],
        ["Collect authorized operational evidence for revocation, logging, and duplicate monitoring."],
    )


def _result(
    rating: int | None,
    critical: bool,
    summary: str,
    evidence: list[str],
    recommendations: list[str],
) -> dict[str, Any]:
    return {
        "rating": rating,
        "critical": critical,
        "summary": summary,
        "evidence": evidence,
        "recommendations": recommendations,
    }


def _public_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        key: policy[key]
        for key in (
            "id",
            "name",
            "version",
            "description",
            "use_case",
            "strictness",
            "minimum_score",
            "minimum_coverage_percent",
            "reject_critical_failures",
        )
    } | {
        "criteria": [
            {
                "id": criterion_id,
                "name": definition["name"],
                "description": definition["description"],
                "max_points": CRITERION_MAX,
                "levels": definition["levels"],
            }
            for criterion_id, definition in CRITERIA.items()
        ]
    }


def _security_fields(card: DetectedCard) -> dict[str, Any]:
    normalized = _as_dict(card.normalized_data_json)
    inspection = _as_dict(normalized.get("inspection"))
    sections = (
        _as_dict(card.raw_output_json),
        _as_dict(normalized.get("raw_output")),
        _as_dict(normalized.get("analysis_fields")),
        _as_dict(normalized.get("security_evidence")),
        _as_dict(inspection.get("combined_fields")),
    )
    fields: dict[str, Any] = {}
    for section in sections:
        fields.update(section)
    observed_keys = _observed_mifare_keys(normalized)
    if observed_keys:
        known_defaults = {
            "000000000000",
            "A0A1A2A3A4A5",
            "B0B1B2B3B4B5",
            "D3F7D3F7D3F7",
            "FFFFFFFFFFFF",
        }
        default_keys = [
            item for item in observed_keys if item["key"] in known_defaults
        ]
        fields.setdefault("observed_key_count", len(observed_keys))
        if default_keys:
            fields.setdefault("default_key_count", len(default_keys))
            fields.setdefault(
                "default_keys",
                sorted({item["key"] for item in default_keys}),
            )
            fields.setdefault(
                "default_key_slots",
                [item["slot"] for item in default_keys],
            )
    return fields


def _observed_mifare_keys(normalized: dict[str, Any]) -> list[dict[str, str]]:
    raw_output = _as_dict(normalized.get("raw_output"))
    inspection_outputs = _as_dict(raw_output.get("inspection_outputs"))
    pattern = re.compile(
        r"Sector\s+(\d+)\s+key\s+([AB])\.{2,}\s*([0-9A-Fa-f]{12})",
        re.IGNORECASE,
    )
    matches: list[dict[str, str]] = []
    for output in inspection_outputs.values():
        if not isinstance(output, str):
            continue
        for sector, key_type, key in pattern.findall(output):
            matches.append(
                {
                    "slot": f"sector-{sector}-key-{key_type.upper()}",
                    "key": key.upper(),
                }
            )
    return matches


def _has_verified_crypto_evidence(fields: dict[str, Any]) -> bool:
    values = {
        _lower_text(fields.get("authentication")),
        _lower_text(fields.get("mutual_authentication")),
        _lower_text(fields.get("secure_messaging")),
    }
    return bool(
        values
        & {
            "verified",
            "enabled",
            "authenticated",
            "active",
            "mutual",
            "mutual_verified",
            "cryptographic",
        }
    )


def _is_modern_family(card: DetectedCard) -> bool:
    family = f"{card.card_type} {card.protocol}".lower()
    return any(
        marker in family
        for marker in (
            "desfire ev1",
            "desfire ev2",
            "desfire ev3",
            "mifare plus",
            "seos",
            "iclass se",
            "cipurse",
            "piv",
        )
    )


def _analyst_review_summary(findings: list[Finding]) -> dict[str, Any]:
    active = [finding for finding in findings if finding.review_status != "false_positive"]
    reviewed = [finding for finding in findings if finding.review_status != "open"]
    unresolved_high = [
        finding
        for finding in active
        if finding.risk_level in {"high", "critical"}
        and finding.review_status != "resolved"
    ]
    if not findings or not reviewed:
        review_status = "not_started"
    elif len(reviewed) == len(findings) and not unresolved_high:
        review_status = "complete"
    else:
        review_status = "in_progress"
    return {
        "status": review_status,
        "finding_count": len(findings),
        "active_finding_count": len(active),
        "reviewed_finding_count": len(reviewed),
        "unresolved_high_count": len(unresolved_high),
    }


def _evaluate_policy_status(
    *,
    score: float | None,
    coverage: int,
    critical_failure: bool,
    policy: dict[str, Any],
) -> tuple[str, bool | None]:
    if coverage < policy["minimum_coverage_percent"]:
        return "insufficient_evidence", None
    if critical_failure and policy["reject_critical_failures"]:
        return "fail", False
    if score is None or score < policy["minimum_score"]:
        return "fail", False
    return "pass", True


def _outcome_for_rating(rating: int | None) -> str:
    return {None: "unknown", 0: "fail", 1: "partial", 2: "pass"}[rating]


def _grade(score: float | None, coverage: int) -> tuple[str, str]:
    if score is None or coverage < GRADE_MINIMUM_COVERAGE:
        return "inconclusive", "Inconclusive"
    if score >= 8.5:
        return "strong", "Strong assurance"
    if score >= 7:
        return "moderate", "Moderate assurance"
    if score >= 5:
        return "limited", "Limited assurance"
    return "weak", "Weak assurance"


def _credential_grade(score: float | None, coverage: int) -> tuple[str, str]:
    if score is None or coverage < 67:
        return "inconclusive", "Credential evidence incomplete"
    if score >= 8.5:
        return "strong", "Strong credential"
    if score >= 7:
        return "moderate", "Moderate credential"
    if score >= 5:
        return "limited", "Limited credential"
    return "weak", "Weak credential"


def _confidence(
    coverage: int,
    context: dict[str, Any],
    operator_evidence: CardAssuranceEvidence | None,
) -> str:
    if operator_evidence and operator_evidence.confidence == "low":
        return "low"
    if operator_evidence and operator_evidence.confidence == "medium" and coverage >= 60:
        return "medium"
    source = _lower_text(context.get("source"))
    reference_only = source in {"simulator", "flipper-import"}
    if coverage >= 80 and not reference_only:
        return "high"
    if coverage >= 60:
        return "medium"
    return "low"


def _operator_evidence_details(record: CardAssuranceEvidence) -> list[str]:
    assessed_at = record.assessed_at.isoformat()
    return [
        f"Operator evidence source: {record.evidence_source}",
        f"Assessed at: {assessed_at}",
        f"Evidence confidence: {record.confidence}",
    ]


def _score_summary(
    *,
    score: float | None,
    lower_bound: int,
    upper_bound: int,
    coverage: int,
    policy_status: str,
    critical_failure: bool,
) -> str:
    displayed_score = "not calculable" if score is None else f"{score}/10"
    status_text = policy_status.replace("_", " ")
    critical_note = " A critical failure is present." if critical_failure else ""
    return (
        f"Provisional score {displayed_score}; possible range {lower_bound}-{upper_bound}/10 "
        f"with {coverage}% evidence coverage. Policy status: {status_text}. "
        "Unknown evidence is reported separately and analyst review does not add security points."
        f"{critical_note}"
    )


def _first_text(fields: dict[str, Any], *names: str) -> str:
    for name in names:
        value = fields.get(name)
        if value is not None and str(value).strip():
            return _lower_text(value)
    return ""


def _first_int(fields: dict[str, Any], *names: str) -> int:
    for name in names:
        value = fields.get(name)
        parsed = _as_int(value)
        if parsed:
            return parsed
    return 0


def _matched_field_evidence(fields: dict[str, Any], *names: str) -> list[str]:
    evidence: list[str] = []
    for name in names:
        if name not in fields:
            continue
        value = fields[name]
        if isinstance(value, (dict, list)):
            rendered = f"{len(value)} item(s)"
        else:
            rendered = str(value)
        evidence.append(f"{name}: {rendered}")
    return evidence


def _contains_any(value: str, *markers: str) -> bool:
    return any(marker in value for marker in markers)


def _nonempty_collection(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"none", "0", "false"}
    return False


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    return _lower_text(value) in {"true", "yes", "1", "enabled", "verified", "active"}


def _is_false(value: Any) -> bool:
    if value is False:
        return True
    return _lower_text(value) in {"false", "no", "0", "disabled", "absent", "none"}


def _deduplicate(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _lower_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0
