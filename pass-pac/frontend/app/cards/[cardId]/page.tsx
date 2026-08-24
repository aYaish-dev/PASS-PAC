"use client";

import Link from "next/link";
import { Database, FileSearch, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getCard,
  getCardAssurance,
  getCardAssuranceEvidence,
  getCardDatasetCorrelation,
  getCardIntelligence,
  getSession,
  listAssurancePolicies,
  listCardFindings,
  deleteCardAssuranceEvidence,
  saveCardAssuranceEvidence,
} from "../../../lib/api";
import type {
  AssurancePolicy,
  CardAssurance,
  CardAssuranceEvidence,
  CardDatasetCorrelation,
  CardIntelligence,
  DetectedCard,
  Finding,
  ScanSession,
} from "../../../lib/api";

const riskStyles: Record<string, string> = {
  informational: "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]",
  low: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
  medium: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  high: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  critical: "border-[#c98b8b] bg-[#ffe5e5] text-[#7f1d1d]",
};

const confidenceStyles: Record<string, string> = {
  exact: "border-[#74a99d] bg-[#e8f5f2] text-[#175f52]",
  strong: "border-[#9ac2b8] bg-[#eef8f5] text-[#1f6f61]",
  moderate: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  weak: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
  none: "border-[#b7c3cc] bg-[#f4f6f7] text-[#52616b]",
};

const assuranceStyles: Record<string, string> = {
  strong: "border-[#74a99d] bg-[#e8f5f2] text-[#175f52]",
  moderate: "border-[#8ab6c5] bg-[#edf7fa] text-[#236276]",
  limited: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  weak: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  inconclusive: "border-[#b7c3cc] bg-[#f4f6f7] text-[#52616b]",
};

const policyStatusStyles: Record<string, string> = {
  pass: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
  fail: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  insufficient_evidence: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
};

const outcomeStyles: Record<string, string> = {
  pass: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
  partial: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  fail: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  unknown: "border-[#b7c3cc] bg-[#f4f6f7] text-[#52616b]",
};

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toDateTimeLocal(value: string) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function resolveCardId(value: string | string[] | undefined) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  const parsedValue = Number(rawValue);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function formatFieldName(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatFieldValue(value: unknown) {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (value === null || value === undefined) {
    return "-";
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export default function CardDetailsPage() {
  const params = useParams<{ cardId?: string | string[] }>();
  const cardId = resolveCardId(params.cardId);

  const [card, setCard] = useState<DetectedCard | null>(null);
  const [session, setSession] = useState<ScanSession | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [datasetCorrelation, setDatasetCorrelation] =
    useState<CardDatasetCorrelation | null>(null);
  const [intelligence, setIntelligence] = useState<CardIntelligence | null>(null);
  const [assurance, setAssurance] = useState<CardAssurance | null>(null);
  const [assuranceEvidence, setAssuranceEvidence] =
    useState<CardAssuranceEvidence | null>(null);
  const [evidenceForm, setEvidenceForm] = useState({
    reader_enforcement: "",
    lifecycle_monitoring: "",
    evidence_source: "",
    confidence: "medium" as CardAssuranceEvidence["confidence"],
    notes: "",
    assessed_at: toDateTimeLocal(new Date().toISOString()),
  });
  const [isEvidenceSaving, setIsEvidenceSaving] = useState(false);
  const [evidenceMessage, setEvidenceMessage] = useState<string | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [assurancePolicies, setAssurancePolicies] = useState<AssurancePolicy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState("university-standard");
  const [isAssuranceLoading, setIsAssuranceLoading] = useState(false);
  const [assuranceError, setAssuranceError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<
    "overview" | "intelligence" | "evidence"
  >("overview");

  useEffect(() => {
    async function loadCard() {
      if (cardId === null) {
        setError("Invalid card id.");
        setIsLoading(false);
        return;
      }

      setError(null);
      setIsLoading(true);
      try {
        const cardData = await getCard(cardId);
        setCard(cardData);
        const [
          sessionData,
          findingData,
          correlationData,
          intelligenceData,
          policyData,
          assuranceData,
          assuranceEvidenceData,
        ] =
          await Promise.all([
            getSession(cardData.session_id),
            listCardFindings(cardId),
            getCardDatasetCorrelation(cardId),
            getCardIntelligence(cardId),
            listAssurancePolicies(),
            getCardAssurance(cardId, "university-standard"),
            getCardAssuranceEvidence(cardId),
          ]);
        setSession(sessionData);
        setFindings(findingData);
        setDatasetCorrelation(correlationData);
        setIntelligence(intelligenceData);
        setAssurancePolicies(policyData);
        setAssurance(assuranceData);
        setAssuranceEvidence(assuranceEvidenceData);
        if (assuranceEvidenceData) {
          setEvidenceForm({
            reader_enforcement: assuranceEvidenceData.reader_enforcement ?? "",
            lifecycle_monitoring: assuranceEvidenceData.lifecycle_monitoring ?? "",
            evidence_source: assuranceEvidenceData.evidence_source,
            confidence: assuranceEvidenceData.confidence,
            notes: assuranceEvidenceData.notes ?? "",
            assessed_at: toDateTimeLocal(assuranceEvidenceData.assessed_at),
          });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load card.");
      } finally {
        setIsLoading(false);
      }
    }

    void loadCard();
  }, [cardId]);

  async function handlePolicyChange(policyId: string) {
    setSelectedPolicy(policyId);
    if (cardId === null) {
      return;
    }
    setAssuranceError(null);
    setIsAssuranceLoading(true);
    try {
      setAssurance(await getCardAssurance(cardId, policyId));
    } catch (err) {
      setAssuranceError(
        err instanceof Error ? err.message : "Unable to evaluate assurance policy.",
      );
    } finally {
      setIsAssuranceLoading(false);
    }
  }

  async function handleEvidenceSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (cardId === null) {
      return;
    }
    if (!evidenceForm.reader_enforcement && !evidenceForm.lifecycle_monitoring) {
      setEvidenceError("Select at least one reader or lifecycle control state.");
      return;
    }

    setIsEvidenceSaving(true);
    setEvidenceError(null);
    setEvidenceMessage(null);
    try {
      const saved = await saveCardAssuranceEvidence(cardId, {
        reader_enforcement:
          (evidenceForm.reader_enforcement || null) as CardAssuranceEvidence["reader_enforcement"],
        lifecycle_monitoring:
          (evidenceForm.lifecycle_monitoring || null) as CardAssuranceEvidence["lifecycle_monitoring"],
        evidence_source: evidenceForm.evidence_source.trim(),
        confidence: evidenceForm.confidence,
        notes: evidenceForm.notes.trim() || null,
        assessed_at: new Date(evidenceForm.assessed_at).toISOString(),
      });
      setAssuranceEvidence(saved);
      setAssurance(await getCardAssurance(cardId, selectedPolicy));
      setEvidenceMessage("Evidence saved and assurance recalculated.");
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Unable to save evidence.");
    } finally {
      setIsEvidenceSaving(false);
    }
  }

  async function handleEvidenceDelete() {
    if (cardId === null || assuranceEvidence === null) {
      return;
    }
    setIsEvidenceSaving(true);
    setEvidenceError(null);
    setEvidenceMessage(null);
    try {
      await deleteCardAssuranceEvidence(cardId);
      setAssuranceEvidence(null);
      setEvidenceForm({
        reader_enforcement: "",
        lifecycle_monitoring: "",
        evidence_source: "",
        confidence: "medium",
        notes: "",
        assessed_at: toDateTimeLocal(new Date().toISOString()),
      });
      setAssurance(await getCardAssurance(cardId, selectedPolicy));
      setEvidenceMessage("Operator evidence removed and assurance recalculated.");
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Unable to remove evidence.");
    } finally {
      setIsEvidenceSaving(false);
    }
  }

  const primaryFinding = findings[0];
  const inspection = asRecord(card?.normalized_data_json.inspection);
  const inspectionFields = asRecord(inspection.combined_fields);
  const rawOutput = asRecord(card?.raw_output_json);
  const inspectionOutputs = asRecord(rawOutput.inspection_outputs);
  const emvReaderOutput =
    typeof inspectionOutputs.hf_emv_reader === "string"
      ? inspectionOutputs.hf_emv_reader
      : "";
  const displayedInspectionFields = { ...inspectionFields };
  const storedPanLastFour = emvReaderOutput.match(
    /\[REDACTED:PAN:LAST4-(\d{4})\]/i,
  );
  if (displayedInspectionFields.pan === undefined && storedPanLastFour) {
    displayedInspectionFields.pan = `•••• ${storedPanLastFour[1]}`;
  }
  if (
    displayedInspectionFields.track_2_equivalent === undefined &&
    /\[REDACTED:TRACK_DATA\]/i.test(emvReaderOutput)
  ) {
    displayedInspectionFields.track_2_equivalent = "Present (redacted)";
  }
  const displayedInspectionFieldEntries = Object.entries(
    displayedInspectionFields,
  ).filter(
    ([key]) =>
      key !== "sensitive_fields_redacted" && key !== "sensitive_data_present",
  );
  const inspectionCommands = Array.isArray(inspection.commands)
    ? inspection.commands.map(asRecord)
    : [];
  const sensitiveEvidenceRedacted =
    inspectionFields.sensitive_data_present === true ||
    storedPanLastFour !== null ||
    /\[REDACTED:TRACK_DATA\]/i.test(emvReaderOutput);

  return (
    <main className="deep-workspace">
      <section className="page-container">
        <header className="page-header">
          <div>
            <p className="text-sm font-semibold uppercase text-[#2f6f73]">
              Card details
            </p>
            <h1 className="mt-3 break-all text-3xl font-semibold text-[#17202a] sm:text-4xl">
              {card?.uid ?? "Detected Card"}
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {session ? (
              <Link
                href={`/sessions/${session.id}`}
                className="inline-flex items-center justify-center rounded-md border border-[#b7c3cc] bg-white px-4 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
              >
                Operator Panel
              </Link>
            ) : null}
            <Link
              href="/sessions"
              className="inline-flex items-center justify-center rounded-md border border-[#b7c3cc] bg-white px-4 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
            >
              Sessions
            </Link>
          </div>
        </header>

        <nav className="workspace-tabs" aria-label="Card detail views">
          {[
            { key: "overview", label: "Security posture", icon: ShieldCheck },
            { key: "intelligence", label: "Intelligence", icon: FileSearch },
            { key: "evidence", label: "Evidence", icon: Database },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                type="button"
                className={`workspace-tab ${activeView === item.key ? "workspace-tab-active" : ""}`}
                onClick={() => setActiveView(item.key as typeof activeView)}
                aria-pressed={activeView === item.key}
              >
                <Icon size={15} aria-hidden="true" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {error ? (
          <div className="mt-6 rounded-md border border-[#e6b8b8] bg-[#fff4f4] px-4 py-3 text-sm font-medium text-[#9b2c2c]">
            {error}
          </div>
        ) : null}

        {isLoading ? (
          <div className="mt-8 rounded-lg border border-[#d8dde3] bg-white p-10 text-center text-sm font-medium text-[#6b7780] shadow-sm">
            Loading card...
          </div>
        ) : card ? (
          <div className="grid min-w-0 gap-5 py-8 lg:grid-cols-[380px_minmax(0,1fr)]">
            <aside className="min-w-0 space-y-5">
              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-lg font-semibold text-[#17202a]">
                    Credential
                  </h2>
                  <span
                    title={card.risk_level === "informational" ? "Contextual observation; not a confirmed vulnerability or a security verdict." : "Finding severity"}
                    className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                      riskStyles[card.risk_level] ??
                      "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                    }`}
                  >
                    {card.risk_level === "informational" ? "Informational observation" : card.risk_level}
                  </span>
                </div>
                <dl className="mt-5 space-y-4 text-sm">
                  <div>
                    <dt className="font-medium text-[#52616b]">UID</dt>
                    <dd className="mt-1 break-all font-mono text-[#17202a]">
                      {card.uid}
                    </dd>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="font-medium text-[#52616b]">Type</dt>
                      <dd className="mt-1 text-[#17202a]">{card.card_type}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-[#52616b]">
                        Technology
                      </dt>
                      <dd className="mt-1 text-[#17202a]">
                        {card.technology}
                      </dd>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="font-medium text-[#52616b]">Frequency</dt>
                      <dd className="mt-1 text-[#17202a]">{card.frequency}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-[#52616b]">Protocol</dt>
                      <dd className="mt-1 text-[#17202a]">{card.protocol}</dd>
                    </div>
                  </div>
                  <div>
                    <dt className="font-medium text-[#52616b]">Detected</dt>
                    <dd className="mt-1 text-[#17202a]">
                      {formatDate(card.created_at)}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Related Session
                </h2>
                {session ? (
                  <div className="mt-5 text-sm">
                    <Link
                      href={`/sessions/${session.id}`}
                      className="font-semibold text-[#17202a] underline-offset-4 transition hover:text-[#2f6f73] hover:underline"
                    >
                      {session.session_name}
                    </Link>
                    <p className="mt-2 text-[#52616b]">
                      {session.description || "-"}
                    </p>
                  </div>
                ) : (
                  <p className="mt-5 text-sm text-[#6b7780]">-</p>
                )}
              </section>

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Risk Finding
                </h2>
                {primaryFinding ? (
                  <div className="mt-4 space-y-4 text-sm leading-6">
                    <div>
                      <span
                        title={primaryFinding.risk_level === "informational" ? "Contextual observation; not a confirmed vulnerability or a security verdict." : "Finding severity"}
                        className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                          riskStyles[primaryFinding.risk_level] ??
                          "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                        }`}
                      >
                        {primaryFinding.risk_level === "informational" ? "Informational observation" : primaryFinding.risk_level}
                      </span>
                      <h3 className="mt-3 font-semibold text-[#17202a]">
                        {primaryFinding.title}
                      </h3>
                      <p className="mt-2 text-[#36454f]">
                        {primaryFinding.description}
                      </p>
                    </div>
                    <div>
                      <p className="font-medium text-[#52616b]">
                        Recommendation
                      </p>
                      <p className="mt-1 text-[#36454f]">
                        {primaryFinding.recommendation}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 text-sm leading-6 text-[#36454f]">
                    No risk finding has been generated for this card yet.
                  </p>
                )}
              </section>
            </aside>

            <section className="min-w-0 space-y-5">
              {assurance ? (
                <section className={`rounded-lg border border-[#cbd6dc] bg-white p-5 shadow-sm ${activeView === "overview" ? "" : "hidden"}`}>
                  <div className="flex flex-col gap-4 border-b border-[#edf0f2] pb-5 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Access Path Security Score
                      </h2>
                      <p className="mt-1 text-sm text-[#52616b]">
                        Versioned 0-10 rubric with explicit evidence coverage and uncertainty.
                      </p>
                    </div>
                    <label className="block w-full sm:w-64">
                      <span className="text-xs font-semibold uppercase text-[#6b7780]">
                        Policy profile
                      </span>
                      <select
                        value={selectedPolicy}
                        onChange={(event) => void handlePolicyChange(event.target.value)}
                        disabled={isAssuranceLoading}
                        className="mt-1 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6] disabled:opacity-60"
                      >
                        {assurancePolicies.map((policy) => (
                          <option key={policy.id} value={policy.id}>
                            {policy.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  {assuranceError ? (
                    <p className="mt-4 rounded-md border border-[#e6b8b8] bg-[#fff4f4] px-4 py-3 text-sm font-medium text-[#9b2c2c]">
                      {assuranceError}
                    </p>
                  ) : null}

                  <div className="mt-5 grid gap-0 border-y border-[#edf0f2] md:grid-cols-2 md:divide-x md:divide-[#edf0f2]">
                    <div className="py-5 md:pr-6">
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Credential technical rating
                      </p>
                      <div className="mt-3 flex items-end justify-between gap-4">
                        <p className="text-4xl font-semibold text-[#17202a]">
                          {assurance.credential_score ?? "-"}
                          <span className="text-base font-medium text-[#6b7780]">/10</span>
                        </p>
                        <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${
                          assuranceStyles[assurance.credential_grade] ?? assuranceStyles.inconclusive
                        }`}>
                          {assurance.credential_grade_label}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-[#52616b]">
                        Authentication, key management, and clone or replay resistance from credential evidence.
                      </p>
                      <p className="mt-2 text-xs font-semibold text-[#52616b]">
                        Credential evidence coverage: {assurance.credential_coverage_percent}%
                      </p>
                    </div>

                    <div className="border-t border-[#edf0f2] py-5 md:border-t-0 md:pl-6">
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Complete access-path assurance
                      </p>
                      <div className="mt-3 flex items-end justify-between gap-4">
                        <p className="text-4xl font-semibold text-[#17202a]">
                          {assurance.score ?? "-"}
                          <span className="text-base font-medium text-[#6b7780]">/10</span>
                        </p>
                        <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${
                          assuranceStyles[assurance.grade] ?? assuranceStyles.inconclusive
                        }`}>
                          {assurance.grade_label}
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-[#52616b]">
                        <span><strong>Range:</strong> {assurance.score_lower_bound}-{assurance.score_upper_bound}/10</span>
                        <span><strong>Coverage:</strong> {assurance.coverage_percent}%</span>
                        <span><strong>Confidence:</strong> {assurance.confidence}</span>
                      </div>
                      <span className={`mt-3 inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                        policyStatusStyles[assurance.policy_status] ?? policyStatusStyles.insufficient_evidence
                      }`}>
                        Policy {assurance.policy_status.replaceAll("_", " ")}
                      </span>
                    </div>
                  </div>

                  <div className="border-b border-[#edf0f2] py-4">
                    <p className="text-sm leading-6 text-[#36454f]">{assurance.summary}</p>
                    <p className="mt-2 text-xs text-[#52616b]">
                      <strong>{assurance.policy.name} v{assurance.policy.version}:</strong>{" "}
                      minimum {assurance.policy.minimum_score}/10 at {assurance.policy.minimum_coverage_percent}% coverage. Method {assurance.methodology_version}.
                    </p>
                  </div>

                  <form onSubmit={handleEvidenceSave} className="border-b border-[#edf0f2] py-5">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <h3 className="font-semibold text-[#17202a]">Deployment control evidence</h3>
                        <p className="mt-1 text-sm text-[#52616b]">
                          Record verified reader, backend, and credential-management controls.
                        </p>
                      </div>
                      {assuranceEvidence ? (
                        <span className="w-fit rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2.5 py-1 text-xs font-semibold text-[#1f6f61]">
                          Evidence #{assuranceEvidence.id}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <label className="block">
                        <span className="text-xs font-semibold uppercase text-[#6b7780]">Reader and backend</span>
                        <select
                          value={evidenceForm.reader_enforcement}
                          onChange={(event) => setEvidenceForm((current) => ({ ...current, reader_enforcement: event.target.value }))}
                          className="mt-1 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6]"
                        >
                          <option value="">Not established</option>
                          <option value="uid_only">UID or static identifier only (0/2)</option>
                          <option value="partial">Partial/backend validation (1/2)</option>
                          <option value="cryptographic">Cryptographic enforcement (2/2)</option>
                        </select>
                      </label>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase text-[#6b7780]">Lifecycle and monitoring</span>
                        <select
                          value={evidenceForm.lifecycle_monitoring}
                          onChange={(event) => setEvidenceForm((current) => ({ ...current, lifecycle_monitoring: event.target.value }))}
                          className="mt-1 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6]"
                        >
                          <option value="">Not established</option>
                          <option value="absent">Controls absent (0/2)</option>
                          <option value="partial">Partial or manual controls (1/2)</option>
                          <option value="managed">Managed controls verified (2/2)</option>
                        </select>
                      </label>
                      <label className="block md:col-span-2">
                        <span className="text-xs font-semibold uppercase text-[#6b7780]">Evidence source</span>
                        <input
                          required
                          minLength={2}
                          maxLength={300}
                          value={evidenceForm.evidence_source}
                          onChange={(event) => setEvidenceForm((current) => ({ ...current, evidence_source: event.target.value }))}
                          placeholder="Authorized reader test, controller configuration, or administrator record"
                          className="mt-1 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] placeholder:text-[#88949c] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6]"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase text-[#6b7780]">Confidence</span>
                        <select
                          value={evidenceForm.confidence}
                          onChange={(event) => setEvidenceForm((current) => ({ ...current, confidence: event.target.value as CardAssuranceEvidence["confidence"] }))}
                          className="mt-1 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6]"
                        >
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                        </select>
                      </label>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase text-[#6b7780]">Assessed at</span>
                        <input
                          required
                          type="datetime-local"
                          value={evidenceForm.assessed_at}
                          onChange={(event) => setEvidenceForm((current) => ({ ...current, assessed_at: event.target.value }))}
                          className="mt-1 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6]"
                        />
                      </label>
                      <label className="block md:col-span-2">
                        <span className="text-xs font-semibold uppercase text-[#6b7780]">Evidence notes</span>
                        <textarea
                          rows={3}
                          maxLength={4000}
                          value={evidenceForm.notes}
                          onChange={(event) => setEvidenceForm((current) => ({ ...current, notes: event.target.value }))}
                          placeholder="Record the observed configuration, test boundary, and supporting reference."
                          className="mt-1 w-full resize-y rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] placeholder:text-[#88949c] focus:border-[#2f6f73] focus:outline-none focus:ring-2 focus:ring-[#b8d5d6]"
                        />
                      </label>
                    </div>

                    {evidenceError ? <p className="mt-3 text-sm font-medium text-[#9b2c2c]">{evidenceError}</p> : null}
                    {evidenceMessage ? <p className="mt-3 text-sm font-medium text-[#1f6f61]">{evidenceMessage}</p> : null}

                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        type="submit"
                        disabled={isEvidenceSaving}
                        className="inline-flex min-h-10 items-center gap-2 rounded-md bg-[#173a63] px-4 py-2 text-sm font-semibold text-white hover:bg-[#102d4e] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <Save size={16} aria-hidden="true" />
                        {isEvidenceSaving ? "Saving" : "Save evidence"}
                      </button>
                      {assuranceEvidence ? (
                        <button
                          type="button"
                          onClick={() => void handleEvidenceDelete()}
                          disabled={isEvidenceSaving}
                          className="inline-flex min-h-10 items-center gap-2 rounded-md border border-[#d8a3a3] bg-white px-4 py-2 text-sm font-semibold text-[#9b2c2c] hover:bg-[#fff4f4] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <Trash2 size={16} aria-hidden="true" />
                          Remove evidence
                        </button>
                      ) : null}
                    </div>
                  </form>

                  <div className="grid gap-4 border-b border-[#edf0f2] py-4 sm:grid-cols-4">
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">Analyst review</p>
                      <p className="mt-1 text-sm font-semibold capitalize text-[#17202a]">
                        {assurance.analyst_review.status.replaceAll("_", " ")}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">Findings</p>
                      <p className="mt-1 text-sm font-semibold text-[#17202a]">
                        {assurance.analyst_review.finding_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">Reviewed</p>
                      <p className="mt-1 text-sm font-semibold text-[#17202a]">
                        {assurance.analyst_review.reviewed_finding_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">Unresolved high</p>
                      <p className={`mt-1 text-sm font-semibold ${
                        assurance.analyst_review.unresolved_high_count > 0
                          ? "text-[#9b2c2c]"
                          : "text-[#1f6f61]"
                      }`}>
                        {assurance.analyst_review.unresolved_high_count}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 divide-y divide-[#edf0f2] border-b border-[#edf0f2]">
                    {assurance.criteria.map((criterion) => (
                      <article key={criterion.id} className="py-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="font-semibold text-[#17202a]">{criterion.name}</h3>
                            <p className="mt-1 text-sm leading-6 text-[#52616b]">
                              {criterion.summary}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <span className="text-xs font-semibold text-[#6b7780]">
                              {criterion.rating ?? "?"}/{criterion.max_points}
                            </span>
                            <span
                              className={`rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                                outcomeStyles[criterion.outcome] ?? outcomeStyles.unknown
                              }`}
                            >
                              {criterion.outcome}
                            </span>
                          </div>
                        </div>
                        {criterion.evidence.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {criterion.evidence.map((item) => (
                              <span
                                key={item}
                                className="rounded-md border border-[#d8dde3] bg-[#fafbfc] px-2 py-1 text-xs text-[#52616b]"
                              >
                                {item}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </article>
                    ))}
                  </div>

                  {assurance.recommendations.length > 0 ? (
                    <div className="mt-5">
                      <h3 className="text-sm font-semibold text-[#17202a]">Priority actions</h3>
                      <ul className="mt-3 space-y-2 text-sm leading-6 text-[#36454f]">
                        {assurance.recommendations.map((recommendation) => (
                          <li key={recommendation} className="border-l-2 border-[#2f6f73] pl-3">
                            {recommendation}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </section>
              ) : null}

              {displayedInspectionFieldEntries.length > 0 || inspectionCommands.length > 0 ? (
                <section className={`rounded-lg border border-[#cbd6dc] bg-white p-5 shadow-sm ${activeView === "overview" ? "" : "hidden"}`}>
                  <div className="flex flex-col gap-3 border-b border-[#edf0f2] pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Family Metadata
                      </h2>
                      <p className="mt-1 text-sm text-[#52616b]">
                        Structured read-only evidence from the selected card-family recipe.
                      </p>
                    </div>
                    <span className="w-fit rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2.5 py-1 text-xs font-semibold text-[#1f6f61]">
                      {String(inspection.profile ?? "metadata-v1")}
                    </span>
                  </div>

                  {sensitiveEvidenceRedacted ? (
                    <div className="mt-4 flex items-start gap-3 rounded-md border border-[#9ac2b8] bg-[#eef8f5] px-4 py-3 text-sm text-[#1f6f61]">
                      <ShieldCheck size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
                      <p>
                        Full account and track values are protected. The masked PAN and retained EMV metadata are shown below.
                      </p>
                    </div>
                  ) : null}

                  {displayedInspectionFieldEntries.length > 0 ? (
                    <dl className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
                      {displayedInspectionFieldEntries.map(([key, value]) => (
                        <div key={key} className="min-w-0 border-b border-[#edf0f2] pb-3">
                          <dt className="text-xs font-semibold uppercase text-[#6b7780]">
                            {formatFieldName(key)}
                          </dt>
                          <dd className="mt-1 break-words font-mono text-sm text-[#17202a]">
                            {formatFieldValue(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="mt-5 text-sm text-[#6b7780]">
                      The metadata commands completed without structured fields.
                    </p>
                  )}

                  <div className="mt-5 flex flex-wrap gap-2">
                    {inspectionCommands.map((command, index) => (
                      <span
                        key={`${String(command.command_key ?? "command")}-${index}`}
                        className={`rounded-md border px-2.5 py-1 font-mono text-xs font-semibold ${
                          command.success
                            ? "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]"
                            : "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]"
                        }`}
                      >
                        {String(command.command ?? command.command_key ?? "metadata command")}
                      </span>
                    ))}
                  </div>
                </section>
              ) : null}

              {intelligence ? (
                <section className={`rounded-lg border border-[#cbd6dc] bg-white p-5 shadow-sm ${activeView === "intelligence" ? "" : "hidden"}`}>
                  <div className="flex flex-col gap-3 border-b border-[#edf0f2] pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Cross-session Intelligence
                      </h2>
                      <p className="mt-1 text-sm text-[#52616b]">
                        Credential fingerprint and repeated-UID comparison.
                      </p>
                    </div>
                    <span
                      className={`w-fit rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                        riskStyles[intelligence.risk_level] ?? riskStyles.informational
                      }`}
                    >
                      {intelligence.risk_level} / {intelligence.confidence}
                    </span>
                  </div>

                  <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Observations
                      </p>
                      <p className="mt-1 text-2xl font-semibold text-[#17202a]">
                        {intelligence.observation_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Sessions
                      </p>
                      <p className="mt-1 text-2xl font-semibold text-[#17202a]">
                        {intelligence.session_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Duplicate UID
                      </p>
                      <p className="mt-1 font-semibold text-[#17202a]">
                        {intelligence.cross_session_duplicate ? "Cross-session" : "Not observed"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Identity consistency
                      </p>
                      <p className="mt-1 font-semibold text-[#17202a]">
                        {intelligence.inconsistent_identity ? "Conflicting" : "Consistent"}
                      </p>
                    </div>
                  </div>

                  <p className="mt-5 text-sm leading-6 text-[#36454f]">
                    {intelligence.summary}
                  </p>
                  <div className="mt-4 flex flex-col gap-1 border-t border-[#edf0f2] pt-4 text-xs sm:flex-row sm:items-center sm:justify-between">
                    <span className="font-semibold uppercase text-[#6b7780]">
                      Fingerprint
                    </span>
                    <code className="break-all text-[#2f6f73]">
                      {intelligence.fingerprint}
                    </code>
                  </div>

                  <div className="mt-4 divide-y divide-[#edf0f2] border-t border-[#edf0f2]">
                    {intelligence.observations.map((observation) => (
                      <article key={observation.card_id} className="py-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <Link
                              href={`/cards/${observation.card_id}`}
                              className="font-semibold text-[#17202a] underline-offset-4 hover:text-[#2f6f73] hover:underline"
                            >
                              Card #{observation.card_id} / Session #{observation.session_id}
                            </Link>
                            <p className="mt-1 text-xs text-[#6b7780]">
                              {formatDate(observation.created_at)} / {observation.source ?? "unknown source"}
                            </p>
                          </div>
                          <code className="break-all text-xs text-[#52616b]">
                            {observation.fingerprint}
                          </code>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {observation.differences.length === 0 ? (
                            <span className="rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2 py-1 text-xs text-[#1f6f61]">
                              Available identity fields consistent
                            </span>
                          ) : (
                            observation.differences.map((difference) => (
                              <span
                                key={`${observation.card_id}-${difference.field}`}
                                className="rounded-md border border-[#e2a6a6] bg-[#fff0f0] px-2 py-1 text-xs text-[#9b2c2c]"
                                title={`${formatFieldValue(difference.target)} -> ${formatFieldValue(difference.observed)}`}
                              >
                                {formatFieldName(difference.field)} changed
                              </span>
                            ))
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}

              {datasetCorrelation ? (
                <section className={`rounded-lg border border-[#cbd6dc] bg-white p-5 shadow-sm ${activeView === "intelligence" ? "" : "hidden"}`}>
                  <div className="flex flex-col gap-3 border-b border-[#edf0f2] pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Dataset Correlation
                      </h2>
                      <p className="mt-1 text-sm text-[#52616b]">
                        Explainable comparison against {datasetCorrelation.evaluated_samples} local samples.
                      </p>
                    </div>
                    <span
                      className={`w-fit rounded-md border px-2.5 py-1 text-xs font-semibold uppercase ${
                        confidenceStyles[datasetCorrelation.confidence] ?? confidenceStyles.none
                      }`}
                    >
                      {datasetCorrelation.best_score}% {datasetCorrelation.confidence}
                    </span>
                  </div>

                  {datasetCorrelation.matches.length === 0 ? (
                    <p className="mt-5 text-sm text-[#6b7780]">
                      No local dataset sample met the minimum similarity threshold.
                    </p>
                  ) : (
                    <div className="mt-2 divide-y divide-[#edf0f2]">
                      {datasetCorrelation.matches.slice(0, 4).map((match) => (
                        <article
                          key={`${match.sample_index}-${match.source_sha256 ?? match.uid ?? match.card_type}`}
                          className="py-4"
                        >
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <h3 className="font-semibold text-[#17202a]">
                                {match.card_type ?? "Dataset sample"}
                              </h3>
                              <p className="mt-1 break-all font-mono text-xs text-[#52616b]">
                                {match.uid ?? "No UID"} / {match.protocol ?? "No protocol"}
                              </p>
                              {match.source_path ? (
                                <p className="mt-1 break-all text-xs text-[#6b7780]">
                                  {match.source_path}
                                </p>
                              ) : null}
                            </div>
                            <span
                              className={`w-fit shrink-0 rounded-md border px-2.5 py-1 text-xs font-semibold uppercase ${
                                confidenceStyles[match.confidence] ?? confidenceStyles.none
                              }`}
                            >
                              {match.score}% {match.confidence}
                            </span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {match.match_details.map((detail) => (
                              <span
                                key={`${match.sample_index}-${detail.field}`}
                                className="rounded-md border border-[#d8dde3] bg-[#fafbfc] px-2 py-1 text-xs text-[#52616b]"
                              >
                                {formatFieldName(detail.field)} +{detail.points}
                              </span>
                            ))}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              ) : null}

              <section className={`rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm ${activeView === "evidence" ? "" : "hidden"}`}>
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Findings Evidence
                </h2>
                {findings.length === 0 ? (
                  <p className="mt-5 text-sm font-medium text-[#6b7780]">
                    No findings evidence available.
                  </p>
                ) : (
                  <div className="mt-5 space-y-4">
                    {findings.map((finding) => (
                      <article
                        key={finding.id}
                        className="min-w-0 rounded-md border border-[#edf0f2] p-4"
                      >
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <h3 className="font-semibold text-[#17202a]">
                              {finding.title}
                            </h3>
                            <p className="mt-1 text-sm text-[#52616b]">
                              {formatDate(finding.created_at)}
                            </p>
                          </div>
                          <span
                            className={`inline-flex w-fit rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                              riskStyles[finding.risk_level] ??
                              "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                            }`}
                          >
                            {finding.risk_level}
                          </span>
                        </div>
                        <pre className="mt-4 max-h-72 max-w-full overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                          {JSON.stringify(finding.evidence_json, null, 2)}
                        </pre>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className={`rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm ${activeView === "evidence" ? "" : "hidden"}`}>
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Normalized Data
                </h2>
                <pre className="mt-5 max-h-[440px] max-w-full overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                  {JSON.stringify(card.normalized_data_json, null, 2)}
                </pre>
              </section>

              <section className={`rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm ${activeView === "evidence" ? "" : "hidden"}`}>
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Raw Output
                </h2>
                <pre className="mt-5 max-h-80 max-w-full overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                  {JSON.stringify(card.raw_output_json, null, 2)}
                </pre>
              </section>
            </section>
          </div>
        ) : (
          <div className="mt-8 rounded-lg border border-[#d8dde3] bg-white p-10 text-center text-sm font-medium text-[#6b7780] shadow-sm">
            Card was not found.
          </div>
        )}
      </section>
    </main>
  );
}
