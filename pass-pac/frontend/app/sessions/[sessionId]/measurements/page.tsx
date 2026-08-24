"use client";

import Link from "next/link";
import {
  BarChart3,
  CheckCircle2,
  ClipboardPlus,
  Database,
  FileSpreadsheet,
  FileText,
  RadioTower,
} from "lucide-react";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { MeasurementAnalysisPanel } from "../../../../components/measurement-analysis-panel";
import {
  compareMeasurementBatches,
  createExperimentBatch,
  deleteMeasurementTrial,
  exportMeasurementCsv,
  exportMeasurementAnalysisCsv,
  exportMeasurementPdf,
  getMeasurementAnalysis,
  getMeasurementSummary,
  getSession,
  getSessionAssurance,
  listExperimentBatches,
  listMeasurementTrials,
  listSessionCards,
  runLiveMeasurementTrial,
  updateExperimentBatch,
} from "../../../../lib/api";
import type {
  DetectedCard,
  ExperimentBatch,
  MeasurementComparison,
  MeasurementAnalysis,
  MeasurementSummary,
  MeasurementTrial,
  ScanSession,
  SessionAssurance,
} from "../../../../lib/api";

const inputClass =
  "mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]";

function formatNumber(value: number | null, suffix = "") {
  return value === null ? "-" : `${value.toLocaleString()}${suffix}`;
}

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function ResearchMeasurementsPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = Number(params.sessionId);
  const [session, setSession] = useState<ScanSession | null>(null);
  const [cards, setCards] = useState<DetectedCard[]>([]);
  const [batches, setBatches] = useState<ExperimentBatch[]>([]);
  const [trials, setTrials] = useState<MeasurementTrial[]>([]);
  const [summary, setSummary] = useState<MeasurementSummary | null>(null);
  const [analysis, setAnalysis] = useState<MeasurementAnalysis | null>(null);
  const [assurance, setAssurance] = useState<SessionAssurance | null>(null);
  const [comparison, setComparison] = useState<MeasurementComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [baselineBatchId, setBaselineBatchId] = useState("");
  const [postRemediationBatchId, setPostRemediationBatchId] = useState("");
  const [activeView, setActiveView] = useState<"overview" | "analysis" | "record" | "dataset">(
    "overview",
  );

  const [batchName, setBatchName] = useState("Baseline credential trials");
  const [condition, setCondition] = useState<"baseline" | "post_remediation">(
    "baseline",
  );
  const [authorizationReference, setAuthorizationReference] = useState("");
  const [operatorLabel, setOperatorLabel] = useState("operator-1");
  const [locationLabel, setLocationLabel] = useState("RFID laboratory");
  const [deviceModel, setDeviceModel] = useState("Proxmark3 Easy 512K");
  const [clientVersion, setClientVersion] = useState("Iceman v4.21611");
  const [firmwareVersion, setFirmwareVersion] = useState("Iceman v4.21611");
  const [antennaConfiguration, setAntennaConfiguration] = useState(
    "Stock LF/HF antennas",
  );
  const [hostOs, setHostOs] = useState("Windows");
  const [commandProfile, setCommandProfile] = useState(
    "read-only-identification-v1",
  );
  const [batchNotes, setBatchNotes] = useState("");

  const [batchId, setBatchId] = useState("");
  const [sourceCardId, setSourceCardId] = useState("");
  const [credentialAlias, setCredentialAlias] = useState("");
  const [trialBand, setTrialBand] = useState<"hf" | "lf">("hf");
  const [distanceCm, setDistanceCm] = useState("0");
  const [orientation, setOrientation] =
    useState<MeasurementTrial["orientation"]>("parallel");
  const [presentedFace, setPresentedFace] =
    useState<MeasurementTrial["presented_face"]>("front");
  const [nearbyMetal, setNearbyMetal] = useState(false);
  const [rfInterference, setRfInterference] =
    useState<MeasurementTrial["rf_interference"]>("none");
  const [trialNotes, setTrialNotes] = useState("");

  const openBatches = useMemo(
    () => batches.filter((batch) => batch.status === "open"),
    [batches],
  );
  const primaryBatch = useMemo(
    () =>
      batches.find((batch) => String(batch.id) === batchId) ??
      openBatches[0] ??
      batches[batches.length - 1] ??
      null,
    [batchId, batches, openBatches],
  );
  const selectedSourceCard = useMemo(
    () => cards.find((card) => String(card.id) === sourceCardId) ?? null,
    [cards, sourceCardId],
  );

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [sessionData, cardData, batchData, trialData, summaryData, analysisData, assuranceData] =
        await Promise.all([
          getSession(sessionId),
          listSessionCards(sessionId),
          listExperimentBatches(sessionId),
          listMeasurementTrials(sessionId),
          getMeasurementSummary(sessionId),
          getMeasurementAnalysis(sessionId),
          getSessionAssurance(sessionId),
        ]);
      setSession(sessionData);
      setCards(cardData);
      setBatches(batchData);
      setTrials(trialData);
      setSummary(summaryData);
      setAnalysis(analysisData);
      setAssurance(assuranceData);
      setBaselineBatchId((current) =>
        batchData.some((batch) => String(batch.id) === current && batch.condition === "baseline")
          ? current
          : String(batchData.find((batch) => batch.condition === "baseline")?.id ?? ""),
      );
      setPostRemediationBatchId((current) =>
        batchData.some((batch) => String(batch.id) === current && batch.condition === "post_remediation")
          ? current
          : String(batchData.find((batch) => batch.condition === "post_remediation")?.id ?? ""),
      );
      setBatchId((current) => {
        if (batchData.some((batch) => String(batch.id) === current && batch.status === "open")) {
          return current;
        }
        const firstOpen = batchData.find((batch) => batch.status === "open");
        return firstOpen ? String(firstOpen.id) : "";
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load measurements.");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (Number.isInteger(sessionId) && sessionId > 0) void refresh();
  }, [refresh, sessionId]);

  async function handleCreateBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActiveAction("create-batch");
    setError(null);
    try {
      const created = await createExperimentBatch(sessionId, {
        name: batchName.trim(),
        condition,
        authorization_reference: authorizationReference.trim(),
        operator_label: operatorLabel.trim(),
        location_label: locationLabel.trim(),
        device_model: deviceModel.trim(),
        client_version: clientVersion.trim(),
        firmware_version: firmwareVersion.trim(),
        antenna_configuration: antennaConfiguration.trim(),
        host_os: hostOs.trim(),
        command_profile: commandProfile.trim(),
        environment_notes: batchNotes.trim() || null,
      });
      setBatchId(String(created.id));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create batch.");
    } finally {
      setActiveAction(null);
    }
  }

  function handleSourceCard(value: string) {
    setSourceCardId(value);
    const card = cards.find((item) => String(item.id) === value);
    if (card) {
      setTrialBand(card.technology.toLowerCase().includes("lf") ? "lf" : "hf");
    }
  }

  async function handleLiveTrial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActiveAction("live-trial");
    setError(null);
    setNotice(null);
    try {
      const result = await runLiveMeasurementTrial(sessionId, {
        batch_id: Number(batchId),
        source_card_id: Number(sourceCardId),
        credential_alias: credentialAlias.trim(),
        band: trialBand,
        distance_cm: Number(distanceCm),
        orientation,
        presented_face: presentedFace,
        nearby_metal: nearbyMetal,
        rf_interference: rfInterference,
        notes: trialNotes.trim() || null,
      });
      setNotice(result.message);
      setTrialNotes("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run live trial.");
    } finally {
      setActiveAction(null);
    }
  }

  async function toggleBatch(batch: ExperimentBatch) {
    const completing = batch.status === "open";
    const confirmed = window.confirm(
      completing
        ? `Complete "${batch.name}"? This locks the batch against new trials until it is reopened.`
        : `Reopen "${batch.name}"? This allows new trials to be added again.`,
    );
    if (!confirmed) return;

    setActiveAction(`batch-${batch.id}`);
    setError(null);
    setNotice(null);
    try {
      await updateExperimentBatch(sessionId, batch.id, {
        status: completing ? "completed" : "open",
      });
      await refresh();
      setNotice(
        completing
          ? `Batch "${batch.name}" completed. New trials are now locked.`
          : `Batch "${batch.name}" reopened. New trials can be recorded.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update batch.");
    } finally {
      setActiveAction(null);
    }
  }

  async function removeTrial(trialId: number) {
    if (!window.confirm("Delete this measurement trial?")) return;
    setActiveAction(`trial-${trialId}`);
    setError(null);
    try {
      await deleteMeasurementTrial(sessionId, trialId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete trial.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleComparison() {
    setActiveAction("compare");
    setError(null);
    setNotice(null);
    try {
      const result = await compareMeasurementBatches(
        sessionId,
        Number(baselineBatchId),
        Number(postRemediationBatchId),
      );
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare batches.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleExport(format: "csv" | "pdf") {
    setActiveAction(`export-${format}`);
    setError(null);
    setNotice(null);
    try {
      const filename =
        format === "csv"
          ? await exportMeasurementCsv(sessionId)
          : await exportMeasurementPdf(
              sessionId,
              baselineBatchId && postRemediationBatchId
                ? Number(baselineBatchId)
                : undefined,
              baselineBatchId && postRemediationBatchId
                ? Number(postRemediationBatchId)
                : undefined,
            );
      setNotice(`${filename} saved to Downloads and the local reports folder.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Unable to export ${format.toUpperCase()}.`);
    } finally {
      setActiveAction(null);
    }
  }

  async function handleAnalysisExport() {
    setActiveAction("export-analysis");
    setError(null);
    setNotice(null);
    try {
      const filename = await exportMeasurementAnalysisCsv(sessionId);
      setNotice(`${filename} saved to Downloads and the local reports folder.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export analysis CSV.");
    } finally {
      setActiveAction(null);
    }
  }

  return (
    <main className="deep-workspace">
      <div className="page-container">
        <header className="page-header">
          <div>
            <p className="text-sm font-semibold uppercase text-[#2f6f73]">
              Controlled experiment workspace
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-[#17202a] sm:text-4xl">
              Research Measurements
            </h1>
            <p className="mt-2 text-sm text-[#52616b]">
              {session?.session_name ?? "Session"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {primaryBatch?.status === "open" ? (
              <button
                type="button"
                onClick={() => void toggleBatch(primaryBatch)}
                disabled={activeAction === `batch-${primaryBatch.id}`}
                className="inline-flex min-h-11 items-center gap-2 rounded-md bg-[#1f6f61] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#195b50] disabled:bg-[#8daaad]"
              >
                <CheckCircle2 size={17} aria-hidden="true" />
                {activeAction === `batch-${primaryBatch.id}`
                  ? "Completing..."
                  : "Complete batch"}
              </button>
            ) : primaryBatch?.status === "completed" ? (
              <span
                role="status"
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-4 py-2 text-sm font-semibold text-[#1f6f61]"
              >
                <CheckCircle2 size={17} aria-hidden="true" />
                Batch completed
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => void handleExport("csv")}
              disabled={activeAction === "export-csv"}
              className="inline-flex min-h-11 items-center gap-2 rounded-md border border-[#315a8a] bg-white px-4 py-2 text-sm font-semibold text-[#315a8a] transition hover:bg-[#eef3fa] disabled:text-[#9ba9ba]"
            >
              <FileSpreadsheet size={17} aria-hidden="true" />
              {activeAction === "export-csv" ? "Exporting..." : "Export CSV"}
            </button>
            <button
              type="button"
              onClick={() => void handleExport("pdf")}
              disabled={activeAction === "export-pdf"}
              className="inline-flex min-h-11 items-center gap-2 rounded-md border border-[#9b2c2c] bg-white px-4 py-2 text-sm font-semibold text-[#9b2c2c] transition hover:bg-[#fff4f4] disabled:text-[#b9a0a0]"
            >
              <FileText size={17} aria-hidden="true" />
              {activeAction === "export-pdf" ? "Exporting..." : "Export PDF"}
            </button>
            <Link
              href={`/sessions/${sessionId}`}
              className="rounded-md bg-[#2f6f73] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#255b5f]"
            >
              Operator Panel
            </Link>
            <Link
              href="/sessions"
              className="rounded-md border border-[#b7c3cc] bg-white px-4 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5]"
            >
              Sessions
            </Link>
          </div>
        </header>

        <nav className="workspace-tabs" aria-label="Research measurement views">
          {[
            { key: "overview", label: "Study overview", icon: BarChart3 },
            { key: "analysis", label: "Analysis", icon: BarChart3 },
            { key: "record", label: "Record measurements", icon: ClipboardPlus },
            { key: "dataset", label: "Dataset", icon: Database },
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
          <div role="alert" className="mt-6 rounded-md border border-[#e6b8b8] bg-[#fff4f4] px-4 py-3 text-sm font-medium text-[#9b2c2c]">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div aria-live="polite" className="mt-6 rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-4 py-3 text-sm font-medium text-[#1f6f61]">
            {notice}
          </div>
        ) : null}

        {loading ? (
          <div className="py-16 text-center text-sm font-medium text-[#6b7780]">
            Loading research measurements...
          </div>
        ) : (
          <>
            <section className={activeView === "overview" ? "py-8" : "hidden"}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                {[
                  ["Trials", summary?.trial_count ?? 0],
                  ["Credentials", summary?.unique_credentials ?? 0],
                  ["Detection", `${summary?.detection_success_rate ?? 0}%`],
                  ["Classification", summary?.classification_accuracy === null ? "-" : `${summary?.classification_accuracy ?? 0}%`],
                  ["Median time", formatNumber(summary?.timing.median_ms ?? null, " ms")],
                ].map(([label, value]) => (
                  <article
                    key={label}
                    className="rounded-md border border-[#d8dde3] bg-white px-4 py-4 shadow-sm"
                  >
                    <p className="text-xs font-semibold uppercase text-[#6b7780]">{label}</p>
                    <p className="mt-2 text-2xl font-semibold text-[#17202a]">{value}</p>
                  </article>
                ))}
              </div>
              <p className="mt-3 text-right text-xs font-medium text-[#6b7780]">
                {summary?.methodology_version ?? "controlled-measurement-v1.0"}
              </p>
            </section>

            <section className={activeView === "overview" ? "border-t border-[#d8dde3] py-8" : "hidden"}>
              <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-[#2f6f73]">Remediation evidence</p>
                  <h2 className="mt-2 text-xl font-semibold text-[#17202a]">Baseline Comparison</h2>
                </div>
                <div className="grid gap-3 sm:grid-cols-[220px_220px_auto]">
                  <label className="text-sm font-medium text-[#36454f]">
                    Baseline batch
                    <select value={baselineBatchId} onChange={(event) => setBaselineBatchId(event.target.value)} className={inputClass}>
                      <option value="">Select baseline</option>
                      {batches.filter((batch) => batch.condition === "baseline").map((batch) => <option key={batch.id} value={batch.id}>{batch.name}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Post-remediation batch
                    <select value={postRemediationBatchId} onChange={(event) => setPostRemediationBatchId(event.target.value)} className={inputClass}>
                      <option value="">Select post-remediation</option>
                      {batches.filter((batch) => batch.condition === "post_remediation").map((batch) => <option key={batch.id} value={batch.id}>{batch.name}</option>)}
                    </select>
                  </label>
                  <button type="button" onClick={() => void handleComparison()} disabled={!baselineBatchId || !postRemediationBatchId || activeAction === "compare"} className="mt-auto rounded-md bg-[#315a8a] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#284b73] disabled:bg-[#9ba9ba]">
                    {activeAction === "compare" ? "Comparing..." : "Compare Batches"}
                  </button>
                </div>
              </div>
              {comparison ? (
                <div className="mt-6">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {[
                      ["Detection delta", `${comparison.detection_rate_delta >= 0 ? "+" : ""}${comparison.detection_rate_delta} pp`],
                      ["Classification delta", comparison.classification_accuracy_delta === null ? "-" : `${comparison.classification_accuracy_delta >= 0 ? "+" : ""}${comparison.classification_accuracy_delta} pp`],
                      ["Median time delta", comparison.median_duration_delta_ms === null ? "-" : `${comparison.median_duration_delta_ms >= 0 ? "+" : ""}${comparison.median_duration_delta_ms} ms`],
                      ["Trial delta", `${comparison.trial_count_delta >= 0 ? "+" : ""}${comparison.trial_count_delta}`],
                    ].map(([label, value]) => <article key={label} className="rounded-md border border-[#d8dde3] bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-[#6b7780]">{label}</p><p className="mt-2 text-xl font-semibold text-[#17202a]">{value}</p></article>)}
                  </div>
                  <div className="mt-4 border-l-4 border-[#2f6f73] bg-white px-4 py-3">
                    {comparison.interpretation.map((item) => <p key={item} className="py-1 text-sm text-[#36454f]">{item}</p>)}
                  </div>
                </div>
              ) : null}
            </section>

            <section className={activeView === "analysis" ? "block" : "hidden"}>
              <MeasurementAnalysisPanel
                analysis={analysis}
                assurance={assurance}
                exporting={activeAction === "export-analysis"}
                onExportAnalysis={() => void handleAnalysisExport()}
              />
            </section>

            <section className={activeView === "record" ? "grid gap-6 border-y border-[#d8dde3] py-8 lg:grid-cols-2" : "hidden"}>
              <form onSubmit={handleCreateBatch} className="rounded-md border border-[#cbd6dc] bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold text-[#17202a]">Experiment Batch</h2>
                  <span className="text-xs font-semibold text-[#52616b]">{batches.length} saved</span>
                </div>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Batch name
                    <input required maxLength={160} value={batchName} onChange={(event) => setBatchName(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Condition
                    <select value={condition} onChange={(event) => setCondition(event.target.value as typeof condition)} className={inputClass}>
                      <option value="baseline">Baseline</option>
                      <option value="post_remediation">Post-remediation</option>
                    </select>
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Authorization reference
                    <input required maxLength={160} value={authorizationReference} onChange={(event) => setAuthorizationReference(event.target.value)} className={inputClass} placeholder="LAB-AUTH-001" />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Operator label
                    <input required value={operatorLabel} onChange={(event) => setOperatorLabel(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Location label
                    <input required value={locationLabel} onChange={(event) => setLocationLabel(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Device model
                    <input required value={deviceModel} onChange={(event) => setDeviceModel(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Host OS
                    <input required value={hostOs} onChange={(event) => setHostOs(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Client version
                    <input required value={clientVersion} onChange={(event) => setClientVersion(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Firmware version
                    <input required value={firmwareVersion} onChange={(event) => setFirmwareVersion(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Antenna configuration
                    <input required value={antennaConfiguration} onChange={(event) => setAntennaConfiguration(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Command profile
                    <input required value={commandProfile} onChange={(event) => setCommandProfile(event.target.value)} className={inputClass} />
                  </label>
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Environment notes
                    <textarea value={batchNotes} onChange={(event) => setBatchNotes(event.target.value)} className={`${inputClass} min-h-20 resize-y`} />
                  </label>
                </div>
                <button disabled={activeAction === "create-batch"} className="mt-5 w-full rounded-md bg-[#2f6f73] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#255b5f] disabled:bg-[#8daaad]">
                  {activeAction === "create-batch" ? "Saving..." : "Create Batch"}
                </button>
              </form>

              <form onSubmit={handleLiveTrial} className="rounded-md border border-[#cbd6dc] bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <RadioTower size={18} className="text-[#2f6f73]" aria-hidden="true" />
                    <h2 className="text-lg font-semibold text-[#17202a]">Live Controlled Trial</h2>
                  </div>
                  <span className="rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2 py-1 text-xs font-semibold text-[#1f6f61]">Read-only</span>
                </div>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Experiment batch
                    <select required value={batchId} onChange={(event) => setBatchId(event.target.value)} className={inputClass}>
                      <option value="">Select an open batch</option>
                      {openBatches.map((batch) => <option key={batch.id} value={batch.id}>{batch.name}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Reference card observation
                    <select required value={sourceCardId} onChange={(event) => handleSourceCard(event.target.value)} className={inputClass}>
                      <option value="">Select the card placed on the antenna</option>
                      {cards.map((card) => <option key={card.id} value={card.id}>#{card.id} {card.card_type} | {card.uid}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Credential alias
                    <input required maxLength={80} value={credentialAlias} onChange={(event) => setCredentialAlias(event.target.value)} className={inputClass} placeholder="CARD-HF-01" />
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Distance (cm)
                    <input required type="number" min="0" max="100" step="0.1" value={distanceCm} onChange={(event) => setDistanceCm(event.target.value)} className={inputClass} />
                  </label>
                  <fieldset className="sm:col-span-2">
                    <legend className="text-sm font-medium text-[#36454f]">Frequency band</legend>
                    <div className="mt-2 inline-flex rounded-md border border-[#b7c3cc] bg-[#f4f6f7] p-1" role="group">
                      {([[
                        "hf",
                        "HF 13.56 MHz",
                      ], [
                        "lf",
                        "LF 125 kHz",
                      ]] as const).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          aria-pressed={trialBand === value}
                          onClick={() => setTrialBand(value)}
                          className={`min-h-9 rounded px-3 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-1 ${
                            trialBand === value
                              ? "bg-white text-[#17202a] shadow-sm"
                              : "text-[#52616b] hover:text-[#17202a]"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                  <label className="text-sm font-medium text-[#36454f]">
                    Orientation
                    <select value={orientation} onChange={(event) => setOrientation(event.target.value as typeof orientation)} className={inputClass}>
                      <option value="parallel">Parallel</option><option value="perpendicular">Perpendicular</option><option value="edge">Edge</option><option value="custom">Custom</option>
                    </select>
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    Presented face
                    <select value={presentedFace} onChange={(event) => setPresentedFace(event.target.value as typeof presentedFace)} className={inputClass}>
                      <option value="front">Front</option><option value="back">Back</option><option value="not_applicable">Not applicable</option>
                    </select>
                  </label>
                  <label className="text-sm font-medium text-[#36454f]">
                    RF interference
                    <select value={rfInterference} onChange={(event) => setRfInterference(event.target.value as typeof rfInterference)} className={inputClass}>
                      <option value="none">None</option><option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option><option value="unknown">Unknown</option>
                    </select>
                  </label>
                  <label className="flex items-center gap-3 rounded-md border border-[#d8dde3] px-3 py-2.5 text-sm font-medium text-[#36454f]">
                    <input type="checkbox" checked={nearbyMetal} onChange={(event) => setNearbyMetal(event.target.checked)} className="h-4 w-4 accent-[#2f6f73]" /> Nearby metal
                  </label>
                  {selectedSourceCard ? (
                    <div className="rounded-md border border-[#d8dde3] bg-[#f7f9fa] px-3 py-2.5 text-sm text-[#36454f]">
                      <p className="font-semibold">{selectedSourceCard.card_type}</p>
                      <p className="mt-1 text-xs text-[#6b7780]">Expected on {trialBand.toUpperCase()} | observation #{selectedSourceCard.id}</p>
                    </div>
                  ) : null}
                  <label className="text-sm font-medium text-[#36454f] sm:col-span-2">
                    Trial notes
                    <textarea value={trialNotes} onChange={(event) => setTrialNotes(event.target.value)} className={`${inputClass} min-h-20 resize-y`} />
                  </label>
                </div>
                <button
                  disabled={
                    !openBatches.length ||
                    !sourceCardId ||
                    !credentialAlias.trim() ||
                    session?.status !== "running" ||
                    activeAction === "live-trial"
                  }
                  className="mt-5 w-full rounded-md bg-[#315a8a] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#284b73] disabled:bg-[#9ba9ba]"
                >
                  {activeAction === "live-trial"
                    ? `Running ${trialBand.toUpperCase()} trial...`
                    : `Run ${trialBand.toUpperCase()} and Record Trial`}
                </button>
              </form>
            </section>

            <section className={activeView === "dataset" ? "py-8" : "hidden"}>
              <div className="flex items-end justify-between gap-4">
                <div><p className="text-xs font-semibold uppercase text-[#2f6f73]">Controlled setup</p><h2 className="mt-2 text-xl font-semibold text-[#17202a]">Experiment Batches</h2></div>
              </div>
              <div className="mt-5 overflow-x-auto rounded-md border border-[#d8dde3] bg-white">
                <table className="w-full min-w-[900px] text-left text-sm">
                  <thead className="bg-[#eef3f4] text-xs uppercase text-[#52616b]"><tr><th className="px-4 py-3">Batch</th><th className="px-4 py-3">Condition</th><th className="px-4 py-3">Setup</th><th className="px-4 py-3">Authorization</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Action</th></tr></thead>
                  <tbody className="divide-y divide-[#edf0f2]">
                    {batches.map((batch) => (
                      <tr key={batch.id}>
                        <td className="px-4 py-3"><p className="font-semibold text-[#17202a]">{batch.name}</p><p className="mt-1 text-xs text-[#6b7780]">{formatDate(batch.started_at)}</p></td>
                        <td className="px-4 py-3 capitalize">{batch.condition.replace("_", " ")}</td>
                        <td className="px-4 py-3"><p>{batch.device_model}</p><p className="mt-1 text-xs text-[#6b7780]">{batch.location_label} | {batch.operator_label}</p></td>
                        <td className="px-4 py-3 font-mono text-xs">{batch.authorization_reference}</td>
                        <td className="px-4 py-3"><span className={`rounded-md border px-2 py-1 text-xs font-semibold ${batch.status === "open" ? "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]" : "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]"}`}>{batch.status}</span></td>
                        <td className="px-4 py-3"><button type="button" disabled={activeAction === `batch-${batch.id}`} onClick={() => void toggleBatch(batch)} className="min-h-11 rounded-md border border-[#b7c3cc] px-3 py-1.5 text-xs font-semibold text-[#36454f] hover:bg-[#f0f3f5] disabled:text-[#9ba9ba]">{batch.status === "open" ? "Complete batch" : "Reopen batch"}</button></td>
                      </tr>
                    ))}
                    {!batches.length ? <tr><td colSpan={6} className="px-4 py-10 text-center text-[#6b7780]">No experiment batches recorded.</td></tr> : null}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={activeView === "dataset" ? "border-y border-[#d8dde3] py-8" : "hidden"}>
              <h2 className="text-xl font-semibold text-[#17202a]">Technology Comparison</h2>
              <div className="mt-5 overflow-x-auto rounded-md border border-[#d8dde3] bg-white">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="bg-[#eef3f4] text-xs uppercase text-[#52616b]"><tr><th className="px-4 py-3">Technology</th><th className="px-4 py-3">Trials</th><th className="px-4 py-3">Credentials</th><th className="px-4 py-3">Detection</th><th className="px-4 py-3">Classification</th><th className="px-4 py-3">Median</th><th className="px-4 py-3">Metadata</th><th className="px-4 py-3">Bytes</th></tr></thead>
                  <tbody className="divide-y divide-[#edf0f2]">
                    {summary?.technologies.map((technology) => <tr key={technology.technology_family}><td className="px-4 py-3 font-semibold">{technology.technology_family}</td><td className="px-4 py-3">{technology.trial_count}</td><td className="px-4 py-3">{technology.unique_credentials}</td><td className="px-4 py-3">{technology.detection_success_rate}%</td><td className="px-4 py-3">{technology.classification_accuracy === null ? "-" : `${technology.classification_accuracy}%`}</td><td className="px-4 py-3">{formatNumber(technology.timing.median_ms, " ms")}</td><td className="px-4 py-3">{technology.average_metadata_fields}</td><td className="px-4 py-3">{technology.total_extracted_bytes}</td></tr>)}
                    {!summary?.technologies.length ? <tr><td colSpan={8} className="px-4 py-10 text-center text-[#6b7780]">No technology measurements available.</td></tr> : null}
                  </tbody>
                </table>
              </div>

              <h3 className="mt-8 text-lg font-semibold text-[#17202a]">Reliable Identification Distance</h3>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {summary?.reliable_distances.map((item) => <article key={`${item.credential_alias}-${item.orientation}-${item.presented_face}`} className="rounded-md border border-[#9ac2b8] bg-[#f5fbf9] p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-[#17202a]">{item.credential_alias}</p><p className="mt-1 text-xs capitalize text-[#52616b]">{item.technology_family} | {item.orientation} | {item.presented_face}</p></div><p className="text-xl font-semibold text-[#1f6f61]">{item.reliable_distance_cm} cm</p></div><p className="mt-3 text-xs font-medium text-[#52616b]">{item.successes} correct of {item.attempts} attempts</p></article>)}
                {!summary?.reliable_distances.length ? <p className="text-sm text-[#6b7780]">No distance condition has reached the repeatability threshold.</p> : null}
              </div>
            </section>

            <section className={activeView === "dataset" ? "py-8" : "hidden"}>
              <div className="flex items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase text-[#2f6f73]">Primary research dataset</p><h2 className="mt-2 text-xl font-semibold text-[#17202a]">Trial Ledger</h2></div><span className="text-sm font-semibold text-[#52616b]">{trials.length} records</span></div>
              <div className="mt-5 overflow-x-auto rounded-md border border-[#d8dde3] bg-white">
                <table className="w-full min-w-[1250px] text-left text-sm">
                  <thead className="bg-[#eef3f4] text-xs uppercase text-[#52616b]"><tr><th className="px-4 py-3">Trial</th><th className="px-4 py-3">Credential</th><th className="px-4 py-3">Technology</th><th className="px-4 py-3">Position</th><th className="px-4 py-3">Detection</th><th className="px-4 py-3">Classification</th><th className="px-4 py-3">Duration</th><th className="px-4 py-3">Evidence</th><th className="px-4 py-3">Recorded</th><th className="px-4 py-3">Action</th></tr></thead>
                  <tbody className="divide-y divide-[#edf0f2]">
                    {trials.map((trial) => <tr key={trial.id}><td className="px-4 py-3 font-mono text-xs">#{trial.trial_number}</td><td className="px-4 py-3"><p className="font-semibold">{trial.credential_alias}</p><p className="mt-1 text-xs text-[#6b7780]">{trial.card_family || "Unspecified family"}</p></td><td className="px-4 py-3">{trial.technology_family}</td><td className="px-4 py-3"><p>{trial.distance_cm} cm | {trial.orientation}</p><p className="mt-1 text-xs capitalize text-[#6b7780]">{trial.presented_face.replace("_", " ")}</p></td><td className="px-4 py-3"><span className={`rounded-md border px-2 py-1 text-xs font-semibold ${trial.success ? "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]" : "border-[#e6b8b8] bg-[#fff4f4] text-[#9b2c2c]"}`}>{trial.success ? "Success" : "Failure"}</span></td><td className="px-4 py-3 capitalize">{trial.classification_result}</td><td className="px-4 py-3">{trial.identification_duration_ms} ms</td><td className="px-4 py-3"><p>{trial.metadata_fields_count} fields | {trial.data_extracted_bytes ?? 0} bytes</p><p className="mt-1 max-w-44 truncate font-mono text-[11px] text-[#6b7780]" title={trial.raw_evidence_sha256 ?? ""}>{trial.raw_evidence_sha256 || "No hash"}</p></td><td className="px-4 py-3 text-xs">{formatDate(trial.created_at)}</td><td className="px-4 py-3"><button type="button" disabled={activeAction === `trial-${trial.id}`} onClick={() => void removeTrial(trial.id)} className="rounded-md border border-[#e6b8b8] px-3 py-1.5 text-xs font-semibold text-[#9b2c2c] hover:bg-[#fff4f4]">Delete</button></td></tr>)}
                    {!trials.length ? <tr><td colSpan={10} className="px-4 py-12 text-center text-[#6b7780]">No measurement trials recorded.</td></tr> : null}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
