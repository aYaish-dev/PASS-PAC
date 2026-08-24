from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.measurement import ExperimentBatch, MeasurementTrial
from app.services.measurement_service import (
    ANALYSIS_VERSION,
    METHODOLOGY_VERSION,
    analyze_measurements,
    compare_measurement_batches,
    list_experiment_batches,
    list_measurement_trials,
    summarize_measurements,
)
from app.services.assurance_service import evaluate_session_assurance
from app.services.session_service import get_session_or_404

REPORT_VERSION = "measurement-report-v1.2"


@dataclass(frozen=True)
class ReportArtifact:
    path: Path
    filename: str
    sha256: str
    content_type: str


def generate_measurement_csv(
    db: Session,
    session_id: int,
    *,
    output_dir: Path | None = None,
) -> ReportArtifact:
    session = get_session_or_404(db, session_id)
    batches = list_experiment_batches(db, session_id)
    trials = list_measurement_trials(db, session_id)
    batch_by_id = {batch.id: batch for batch in batches}
    path = _report_path(session_id, "measurements", "csv", output_dir)

    columns = [
        "report_version",
        "methodology_version",
        "session_id",
        "session_name",
        "batch_id",
        "batch_name",
        "condition",
        "batch_status",
        "batch_completed_at",
        "authorization_reference",
        "operator_label",
        "location_label",
        "device_model",
        "client_version",
        "firmware_version",
        "antenna_configuration",
        "host_os",
        "command_profile",
        "trial_id",
        "trial_number",
        "credential_alias",
        "technology_family",
        "card_family",
        "distance_cm",
        "orientation",
        "presented_face",
        "success",
        "classification_result",
        "identification_duration_ms",
        "metadata_fields_count",
        "data_extracted_bytes",
        "nearby_metal",
        "rf_interference",
        "environment_notes",
        "trial_notes",
        "evidence_sha256",
        "recorded_at",
    ]
    ordered_trials = sorted(
        trials,
        key=lambda trial: (
            trial.batch_id,
            trial.credential_alias,
            trial.trial_number,
        ),
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for trial in ordered_trials:
            batch = batch_by_id[trial.batch_id]
            writer.writerow(
                {
                    "report_version": REPORT_VERSION,
                    "methodology_version": METHODOLOGY_VERSION,
                    "session_id": session.id,
                    "session_name": session.session_name,
                    "batch_id": batch.id,
                    "batch_name": batch.name,
                    "condition": batch.condition,
                    "batch_status": batch.status,
                    "batch_completed_at": (
                        batch.completed_at.isoformat() if batch.completed_at else ""
                    ),
                    "authorization_reference": batch.authorization_reference,
                    "operator_label": batch.operator_label,
                    "location_label": batch.location_label,
                    "device_model": batch.device_model,
                    "client_version": batch.client_version,
                    "firmware_version": batch.firmware_version,
                    "antenna_configuration": batch.antenna_configuration,
                    "host_os": batch.host_os,
                    "command_profile": batch.command_profile,
                    "trial_id": trial.id,
                    "trial_number": trial.trial_number,
                    "credential_alias": trial.credential_alias,
                    "technology_family": trial.technology_family,
                    "card_family": trial.card_family or "",
                    "distance_cm": trial.distance_cm,
                    "orientation": trial.orientation,
                    "presented_face": trial.presented_face,
                    "success": str(trial.success).lower(),
                    "classification_result": trial.classification_result,
                    "identification_duration_ms": trial.identification_duration_ms,
                    "metadata_fields_count": trial.metadata_fields_count,
                    "data_extracted_bytes": trial.data_extracted_bytes,
                    "nearby_metal": str(trial.nearby_metal).lower(),
                    "rf_interference": trial.rf_interference,
                    "environment_notes": trial.environment_notes or "",
                    "trial_notes": trial.notes or "",
                    "evidence_sha256": trial.raw_evidence_sha256 or "",
                    "recorded_at": trial.created_at.isoformat(),
                }
            )
    return _artifact(path, "text/csv")


def generate_measurement_analysis_csv(
    db: Session,
    session_id: int,
    *,
    output_dir: Path | None = None,
) -> ReportArtifact:
    session = get_session_or_404(db, session_id)
    analysis = analyze_measurements(db, session_id)
    reliable_by_alias = {
        item["credential_alias"]: item["reliable_identification_distance_cm"]
        for item in analysis["credentials"]
    }
    path = _report_path(session_id, "measurement-analysis", "csv", output_dir)
    columns = [
        "report_version",
        "analysis_version",
        "methodology_version",
        "session_id",
        "session_name",
        "credential_alias",
        "technology_family",
        "card_family",
        "distance_cm",
        "orientation",
        "presented_face",
        "attempts",
        "meets_minimum_repetitions",
        "detection_events",
        "detection_rate_percent",
        "detection_ci95_lower_percent",
        "detection_ci95_upper_percent",
        "correct_identification_events",
        "correct_identification_rate_percent",
        "correct_identification_ci95_lower_percent",
        "correct_identification_ci95_upper_percent",
        "partial_response_count",
        "incorrect_classification_count",
        "inconclusive_count",
        "correct_identification_median_ms",
        "correct_identification_q1_ms",
        "correct_identification_q3_ms",
        "reliable_identification_distance_cm",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for condition in analysis["conditions"]:
            detection = condition["detection"]
            correct = condition["correct_identification"]
            timing = condition["correct_identification_timing"]
            writer.writerow(
                {
                    "report_version": REPORT_VERSION,
                    "analysis_version": analysis["analysis_version"],
                    "methodology_version": analysis["methodology_version"],
                    "session_id": session.id,
                    "session_name": session.session_name,
                    "credential_alias": condition["credential_alias"],
                    "technology_family": condition["technology_family"],
                    "card_family": condition["card_family"] or "",
                    "distance_cm": condition["distance_cm"],
                    "orientation": condition["orientation"],
                    "presented_face": condition["presented_face"],
                    "attempts": detection["attempts"],
                    "meets_minimum_repetitions": str(
                        condition["meets_minimum_repetitions"]
                    ).lower(),
                    "detection_events": detection["events"],
                    "detection_rate_percent": detection["rate_percent"],
                    "detection_ci95_lower_percent": detection["ci_lower_percent"],
                    "detection_ci95_upper_percent": detection["ci_upper_percent"],
                    "correct_identification_events": correct["events"],
                    "correct_identification_rate_percent": correct["rate_percent"],
                    "correct_identification_ci95_lower_percent": correct["ci_lower_percent"],
                    "correct_identification_ci95_upper_percent": correct["ci_upper_percent"],
                    "partial_response_count": condition["partial_response_count"],
                    "incorrect_classification_count": condition[
                        "incorrect_classification_count"
                    ],
                    "inconclusive_count": condition["inconclusive_count"],
                    "correct_identification_median_ms": timing["median_ms"],
                    "correct_identification_q1_ms": timing["q1_ms"],
                    "correct_identification_q3_ms": timing["q3_ms"],
                    "reliable_identification_distance_cm": reliable_by_alias.get(
                        condition["credential_alias"]
                    ),
                }
            )
    return _artifact(path, "text/csv")


def generate_measurement_pdf(
    db: Session,
    session_id: int,
    *,
    baseline_batch_id: int | None = None,
    post_remediation_batch_id: int | None = None,
    output_dir: Path | None = None,
) -> ReportArtifact:
    if (baseline_batch_id is None) != (post_remediation_batch_id is None):
        raise ValueError(
            "Both baseline and post-remediation batch IDs are required for comparison."
        )

    session = get_session_or_404(db, session_id)
    batches = list_experiment_batches(db, session_id)
    trials = list_measurement_trials(db, session_id)
    summary = summarize_measurements(db, session_id)
    analysis = analyze_measurements(db, session_id)
    assurance = evaluate_session_assurance(db, session_id)
    comparison = None
    if baseline_batch_id is not None and post_remediation_batch_id is not None:
        comparison = compare_measurement_batches(
            db,
            session_id,
            baseline_batch_id,
            post_remediation_batch_id,
        )

    path = _report_path(session_id, "research-report", "pdf", output_dir)
    styles = _pdf_styles()
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=f"PASS-PAC Measurement Report - Session {session_id}",
        author="PASS-PAC",
        subject="Authorized RFID/NFC controlled measurement report",
    )
    story: list[Any] = []
    generated_at = datetime.now(timezone.utc)

    story.extend(
        [
            Paragraph("PASS-PAC", styles["brand"]),
            Paragraph("Controlled RFID/NFC Measurement Report", styles["title"]),
            Paragraph(_escape(session.session_name), styles["subtitle"]),
            Spacer(1, 5 * mm),
            _key_value_table(
                [
                    ("Session", str(session.id)),
                    ("Environment", session.environment),
                    ("Generated (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")),
                    ("Methodology", METHODOLOGY_VERSION),
                    ("Report version", REPORT_VERSION),
                ],
                styles,
            ),
            Spacer(1, 5 * mm),
            Paragraph(
                "Research-safe export: operational UIDs, raw device output, keys, and door mappings are excluded. Credential aliases and SHA-256 evidence hashes are retained.",
                styles["notice"],
            ),
            Spacer(1, 7 * mm),
            Paragraph("Executive Summary", styles["heading"]),
            _summary_table(summary, styles),
            Spacer(1, 5 * mm),
            Paragraph(
                "Results describe only the authorized credentials, equipment, positioning, and environmental conditions recorded in this session. They are not a universal property of a card technology or a certification of the complete access-control deployment.",
                styles["body"],
            ),
            Spacer(1, 6 * mm),
            Paragraph("Method", styles["heading"]),
            Paragraph(
                "One trial represents one bounded credential presentation. Detection rate includes successful and failed attempts. Classification accuracy excludes inconclusive labels. Timing statistics use successful identifications. Reliable identification distance is the greatest tested distance with at least five attempts, at least four successful and correctly classified identifications, and at least 80 percent correct identification for the same alias, orientation, and presented face.",
                styles["body"],
            ),
        ]
    )

    story.extend(_batch_section(batches, styles))
    story.extend(_technology_section(summary, styles))
    story.extend(_distance_section(summary, styles))
    story.extend(_statistical_analysis_section(analysis, styles))
    story.extend(_assurance_section(assurance, analysis, styles))
    if comparison is not None:
        story.extend(_comparison_section(comparison, styles))
    story.extend(_trial_appendix(trials, styles))
    story.extend(
        [
            Spacer(1, 5 * mm),
            Paragraph("Limitations", styles["heading"]),
            Paragraph(
                "Descriptive differences are not statistical significance claims. RF interference, antenna placement, card orientation, device warm-up, and operator procedure may affect results. Empty or incomplete fields must be reported as missing evidence rather than interpreted as secure or insecure behavior.",
                styles["body"],
            ),
        ]
    )

    document.build(
        story,
        onFirstPage=lambda canvas, doc: _page_chrome(canvas, doc, session_id),
        onLaterPages=lambda canvas, doc: _page_chrome(canvas, doc, session_id),
    )
    return _artifact(path, "application/pdf")


def _batch_section(
    batches: list[ExperimentBatch], styles: dict[str, ParagraphStyle]
) -> list[Any]:
    rows: list[list[Any]] = [["Batch", "Condition", "Status", "Equipment", "Control"]]
    for batch in sorted(batches, key=lambda item: item.id):
        rows.append(
            [
                Paragraph(_escape(batch.name), styles["table"]),
                batch.condition.replace("_", " "),
                Paragraph(
                    _lines(
                        batch.status,
                        batch.completed_at.strftime("%Y-%m-%d %H:%M UTC")
                        if batch.completed_at
                        else "not finalized",
                    ),
                    styles["table"],
                ),
                Paragraph(
                    _lines(
                        batch.device_model,
                        batch.client_version,
                        batch.firmware_version,
                    ),
                    styles["table"],
                ),
                Paragraph(
                    _lines(
                        batch.authorization_reference,
                        batch.operator_label,
                        batch.location_label,
                    ),
                    styles["table"],
                ),
            ]
        )
    if len(rows) == 1:
        rows.append(["No batches", "-", "-", "-", "-"])
    return [
        Spacer(1, 6 * mm),
        Paragraph("Controlled Setups", styles["heading"]),
        _styled_table(rows, [36 * mm, 24 * mm, 28 * mm, 47 * mm, 41 * mm]),
    ]


def _technology_section(summary: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    rows = [["Technology", "Trials", "Credentials", "Detection", "Classification", "Median"]]
    for item in summary["technologies"]:
        rows.append(
            [
                Paragraph(_escape(item["technology_family"]), styles["table"]),
                item["trial_count"],
                item["unique_credentials"],
                f"{item['detection_success_rate']:.2f}%",
                _percent_or_dash(item["classification_accuracy"]),
                _number_or_dash(item["timing"]["median_ms"], " ms"),
            ]
        )
    if len(rows) == 1:
        rows.append(["No measurements", "0", "0", "-", "-", "-"])
    return [
        Spacer(1, 6 * mm),
        Paragraph("Technology Comparison", styles["heading"]),
        _styled_table(rows, [45 * mm, 20 * mm, 25 * mm, 30 * mm, 32 * mm, 24 * mm]),
    ]


def _distance_section(summary: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    rows = [["Credential", "Technology", "Orientation", "Face", "Distance", "Correct / attempts"]]
    for item in summary["reliable_distances"]:
        rows.append(
            [
                item["credential_alias"],
                item["technology_family"],
                item["orientation"],
                item["presented_face"].replace("_", " "),
                f"{item['reliable_distance_cm']:g} cm",
                f"{item['successes']} / {item['attempts']}",
            ]
        )
    if len(rows) == 1:
        rows.append(["No qualifying condition", "-", "-", "-", "-", "-"])
    return [
        Spacer(1, 6 * mm),
        Paragraph("Reliable Identification Distance", styles["heading"]),
        _styled_table(rows, [34 * mm, 34 * mm, 30 * mm, 27 * mm, 27 * mm, 24 * mm]),
    ]


def _statistical_analysis_section(
    analysis: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> list[Any]:
    credential_rows: list[list[Any]] = [
        ["Credential", "Trials", "Detection (95% CI)", "Correct ID (95% CI)", "Reliable", "Median / IQR"]
    ]
    for item in analysis["credentials"]:
        detection = item["detection"]
        correct = item["correct_identification"]
        timing = item["correct_identification_timing"]
        credential_rows.append(
            [
                Paragraph(_escape(item["credential_alias"]), styles["table"]),
                item["trial_count"],
                f"{detection['rate_percent']:.1f}% ({detection['ci_lower_percent']:.1f}-{detection['ci_upper_percent']:.1f})",
                f"{correct['rate_percent']:.1f}% ({correct['ci_lower_percent']:.1f}-{correct['ci_upper_percent']:.1f})",
                (
                    "not established"
                    if item["reliable_identification_distance_cm"] is None
                    else f"{item['reliable_identification_distance_cm']:g} cm"
                ),
                (
                    "-"
                    if timing["median_ms"] is None
                    else f"{timing['median_ms']:g} / {timing['q1_ms']:g}-{timing['q3_ms']:g} ms"
                ),
            ]
        )

    condition_rows: list[list[Any]] = [
        ["Alias", "Distance", "Attempts", "Detected", "Correct ID", "Correct 95% CI", "Partial"]
    ]
    for item in analysis["conditions"]:
        detection = item["detection"]
        correct = item["correct_identification"]
        condition_rows.append(
            [
                item["credential_alias"],
                f"{item['distance_cm']:g} cm",
                detection["attempts"],
                f"{detection['events']} ({detection['rate_percent']:.1f}%)",
                f"{correct['events']} ({correct['rate_percent']:.1f}%)",
                f"{correct['ci_lower_percent']:.1f}-{correct['ci_upper_percent']:.1f}%",
                item["partial_response_count"],
            ]
        )

    elements: list[Any] = [
        Paragraph("Baseline Statistical Analysis", styles["heading"]),
        Paragraph(
            _escape(
                f"{analysis['analysis_version']} uses Wilson 95% confidence intervals, "
                f"a minimum of {analysis['minimum_attempts_per_condition']} attempts per condition, "
                "and median with interquartile range for correct-identification timing."
            ),
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        _analysis_rate_chart(analysis),
        Spacer(1, 4 * mm),
        _styled_table(credential_rows, [28 * mm, 14 * mm, 42 * mm, 42 * mm, 23 * mm, 30 * mm], font_size=7),
        Spacer(1, 5 * mm),
        Paragraph("Condition-level Results", styles["heading"]),
        _styled_table(condition_rows, [29 * mm, 21 * mm, 19 * mm, 30 * mm, 30 * mm, 31 * mm, 18 * mm], font_size=7),
        Spacer(1, 5 * mm),
        Paragraph("Automated Data Quality Review", styles["heading"]),
    ]
    if analysis["quality_flags"]:
        for flag in analysis["quality_flags"]:
            elements.append(
                Paragraph(
                    f"<b>{_escape(flag['severity'].upper())}: {_escape(flag['title'])}</b><br/>{_escape(flag['detail'])}",
                    styles["body"],
                )
            )
    else:
        elements.append(Paragraph("No automated quality flags were raised.", styles["body"]))
    return elements


def _analysis_rate_chart(analysis: dict[str, Any]) -> Drawing:
    rows = analysis["credentials"]
    drawing = Drawing(176 * mm, max(40 * mm, (len(rows) * 21 + 38) * mm / 3))
    bar_left = 38 * mm
    bar_width = 118 * mm
    row_height = 20
    top = drawing.height - 18
    drawing.add(String(0, top + 5, "Credential-level rates", fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#17202A")))
    drawing.add(Rect(bar_left, top + 2, 8, 6, fillColor=colors.HexColor("#315A8A"), strokeColor=None))
    drawing.add(String(bar_left + 11, top + 2, "Detection", fontSize=7, fillColor=colors.HexColor("#52616B")))
    drawing.add(Rect(bar_left + 55, top + 2, 8, 6, fillColor=colors.HexColor("#1F6F61"), strokeColor=None))
    drawing.add(String(bar_left + 66, top + 2, "Correct ID", fontSize=7, fillColor=colors.HexColor("#52616B")))
    for index, item in enumerate(rows):
        y = top - 18 - index * row_height
        drawing.add(String(0, y + 4, item["credential_alias"][:18], fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor("#17202A")))
        drawing.add(Rect(bar_left, y + 7, bar_width, 5, fillColor=colors.HexColor("#E9EEF3"), strokeColor=None))
        drawing.add(Rect(bar_left, y + 7, bar_width * item["detection"]["rate_percent"] / 100, 5, fillColor=colors.HexColor("#315A8A"), strokeColor=None))
        drawing.add(Rect(bar_left, y, bar_width, 5, fillColor=colors.HexColor("#E5EFED"), strokeColor=None))
        drawing.add(Rect(bar_left, y, bar_width * item["correct_identification"]["rate_percent"] / 100, 5, fillColor=colors.HexColor("#1F6F61"), strokeColor=None))
        drawing.add(String(bar_left + bar_width + 4, y + 2, f"{item['detection']['rate_percent']:.0f}% / {item['correct_identification']['rate_percent']:.0f}%", fontSize=7, fillColor=colors.HexColor("#52616B")))
    return drawing


def _assurance_section(
    assurance: dict[str, Any],
    analysis: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    alias_by_card_id = {
        item["source_card_id"]: item["credential_alias"]
        for item in analysis["credentials"]
        if item["source_card_id"] is not None
    }
    rows: list[list[Any]] = [
        ["Credential", "Card family", "Credential", "Access path", "Evidence range", "Coverage", "Policy", "Critical"]
    ]
    for card in assurance["cards"]:
        rows.append(
            [
                alias_by_card_id.get(card["card_id"], f"Card {card['card_id']}"),
                Paragraph(_escape(card["card_type"]), styles["table"]),
                "not calculable" if card["credential_score"] is None else f"{card['credential_score']:g}/10",
                "not calculable" if card["score"] is None else f"{card['score']:g}/10",
                f"{card['score_lower_bound']}-{card['score_upper_bound']}/10",
                f"{card['coverage_percent']}%",
                card["policy_status"].replace("_", " "),
                "yes" if card["critical_failure"] else "no",
            ]
        )
    return [
        Spacer(1, 7 * mm),
        Paragraph("Credential and Access Path Security Scores v2.1", styles["heading"]),
        Paragraph(
            "The credential rating summarizes authentication strength, key management, and clone/replay resistance. The complete access-path result adds reader/backend enforcement and lifecycle monitoring. Operator-supplied deployment controls require a dated evidence source and confidence level. Scores remain provisional when controls are unknown; coverage and lower-to-upper bounds prevent missing evidence from being treated as security. RF performance is intentionally excluded.",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        _styled_table(rows, [24 * mm, 31 * mm, 21 * mm, 21 * mm, 23 * mm, 17 * mm, 26 * mm, 15 * mm], font_size=6.5),
        Spacer(1, 3 * mm),
        Paragraph(_escape(assurance["summary"]), styles["body"]),
    ]


def _comparison_section(comparison: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    baseline = comparison["baseline_summary"]
    post = comparison["post_remediation_summary"]
    rows = [
        ["Metric", "Baseline", "Post-remediation", "Delta"],
        [
            "Trials",
            baseline["trial_count"],
            post["trial_count"],
            f"{comparison['trial_count_delta']:+d}",
        ],
        [
            "Detection rate",
            f"{baseline['detection_success_rate']:.2f}%",
            f"{post['detection_success_rate']:.2f}%",
            f"{comparison['detection_rate_delta']:+.2f} pp",
        ],
        [
            "Classification accuracy",
            _percent_or_dash(baseline["classification_accuracy"]),
            _percent_or_dash(post["classification_accuracy"]),
            _number_or_dash(comparison["classification_accuracy_delta"], " pp", signed=True),
        ],
        [
            "Median successful time",
            _number_or_dash(baseline["timing"]["median_ms"], " ms"),
            _number_or_dash(post["timing"]["median_ms"], " ms"),
            _number_or_dash(comparison["median_duration_delta_ms"], " ms", signed=True),
        ],
    ]
    elements: list[Any] = [
        Spacer(1, 7 * mm),
        Paragraph("Baseline vs Post-remediation", styles["heading"]),
        Paragraph(
            _escape(
                f"{comparison['baseline_batch'].name} compared with "
                f"{comparison['post_remediation_batch'].name}."
            ),
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        _styled_table(rows, [55 * mm, 40 * mm, 45 * mm, 36 * mm]),
        Spacer(1, 4 * mm),
    ]
    for item in comparison["interpretation"]:
        elements.append(Paragraph(f"- {_escape(item)}", styles["body"]))
    return elements


def _trial_appendix(trials: list[MeasurementTrial], styles: dict[str, ParagraphStyle]) -> list[Any]:
    rows: list[list[Any]] = [["Alias / Trial", "Technology", "Position", "Result", "Class", "Time", "Evidence"]]
    for trial in sorted(
        trials,
        key=lambda item: (item.credential_alias, item.trial_number),
    ):
        rows.append(
            [
                Paragraph(
                    _escape(f"{trial.credential_alias} / {trial.trial_number}"),
                    styles["table"],
                ),
                Paragraph(_escape(trial.technology_family), styles["table"]),
                Paragraph(
                    _lines(
                        f"{trial.distance_cm:g} cm",
                        trial.orientation,
                        trial.presented_face,
                    ),
                    styles["table"],
                ),
                "Success" if trial.success else "Failure",
                trial.classification_result,
                f"{trial.identification_duration_ms} ms",
                (trial.raw_evidence_sha256 or "none")[:12],
            ]
        )
    if len(rows) == 1:
        rows.append(["No trials", "-", "-", "-", "-", "-", "-"])
    return [
        PageBreak(),
        Paragraph("Trial-level Appendix", styles["heading"]),
        Paragraph(
            "All attempts are retained. Evidence values are SHA-256 prefixes, not credential identifiers.",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        _styled_table(
            rows,
            [31 * mm, 24 * mm, 30 * mm, 24 * mm, 20 * mm, 20 * mm, 27 * mm],
            font_size=7,
        ),
    ]


def _summary_table(summary: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["Trials", "Credentials", "Detection", "Classification", "Median time"],
        [
            summary["trial_count"],
            summary["unique_credentials"],
            f"{summary['detection_success_rate']:.2f}%",
            _percent_or_dash(summary["classification_accuracy"]),
            _number_or_dash(summary["timing"]["median_ms"], " ms"),
        ],
    ]
    return _styled_table(rows, [35 * mm] * 5, font_size=9)


def _key_value_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [Paragraph(_escape(label), styles["table_label"]), Paragraph(_escape(value), styles["table"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[45 * mm, 130 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#D8DDE3")),
            ]
        )
    )
    return table


def _styled_table(
    rows: list[list[Any]],
    widths: list[float],
    *,
    font_size: int = 8,
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F6F73")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD6DC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8F9")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "Brand",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.HexColor("#2F6F73"),
            spaceAfter=3,
        ),
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=colors.HexColor("#17202A"),
            alignment=TA_CENTER,
            spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            textColor=colors.HexColor("#52616B"),
            alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            "Heading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#17202A"),
            spaceBefore=4,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#36454F"),
            spaceAfter=3,
        ),
        "notice": ParagraphStyle(
            "Notice",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#315A8A"),
            borderColor=colors.HexColor("#B8C4D6"),
            borderWidth=0.6,
            borderPadding=7,
            backColor=colors.HexColor("#EEF3FA"),
        ),
        "table": ParagraphStyle(
            "TableText",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#17202A"),
        ),
        "table_label": ParagraphStyle(
            "TableLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.HexColor("#52616B"),
        ),
    }


def _page_chrome(canvas: Any, document: Any, session_id: int) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(colors.HexColor("#D8DDE3"))
    canvas.setLineWidth(0.4)
    canvas.line(17 * mm, 14 * mm, width - 17 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7780"))
    canvas.drawString(17 * mm, 9 * mm, f"PASS-PAC | Session {session_id} | Local authorized assessment")
    canvas.drawRightString(width - 17 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def _report_path(
    session_id: int,
    label: str,
    extension: str,
    output_dir: Path | None,
) -> Path:
    root = output_dir or Path(get_settings().reports_dir)
    session_dir = root / f"session-{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return session_dir / f"pass-pac-session-{session_id}-{label}-{timestamp}.{extension}"


def _artifact(path: Path, content_type: str) -> ReportArtifact:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ReportArtifact(
        path=path,
        filename=path.name,
        sha256=digest,
        content_type=content_type,
    )


def _percent_or_dash(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"


def _number_or_dash(
    value: float | None,
    suffix: str,
    *,
    signed: bool = False,
) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}{suffix}" if signed else f"{value:.2f}{suffix}"


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _lines(*values: str) -> str:
    return "<br/>".join(_escape(value) for value in values)
