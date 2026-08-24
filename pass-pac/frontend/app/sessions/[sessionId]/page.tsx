"use client";

import Link from "next/link";
import { Activity, BarChart3, Compass, Database, RadioTower } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { GuidedEvidencePanel } from "../../../components/guided-evidence-panel";
import {
  deleteSession,
  analyzeSessionDeviceTraceBuffer,
  analyzeSessionTransactionTrace,
  getSessionTransactionTrace,
  getSessionAssurance,
  getSessionCapabilities,
  getSessionEvidenceGuidance,
  getSession,
  listAssurancePolicies,
  listSessionAssessments,
  listSessionCards,
  listSessionFindings,
  listSessionOperatorCommands,
  listSessionOperatorRecipes,
  listSessionTransactionTraces,
  runSessionOperatorCommand,
  runSessionOperatorRecipe,
  simulateSessionScan,
  startAutomatedAssessment,
  startSession,
  stopSession,
  updateFinding,
} from "../../../lib/api";
import type {
  AssurancePolicy,
  AssessmentRun,
  CapabilityRegistry,
  DetectedCard,
  Finding,
  FindingReviewStatus,
  GuidedEvidence,
  OperatorCommand,
  OperatorRecipe,
  OperatorRecipeRun,
  ScanSession,
  SessionAssurance,
  TraceProtocol,
  TransactionTrace,
  TransactionTraceSummary,
} from "../../../lib/api";

const statusStyles: Record<string, string> = {
  created: "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]",
  running: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
  completed: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
};

const riskStyles: Record<string, string> = {
  informational: "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]",
  low: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
  medium: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  high: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  critical: "border-[#c98b8b] bg-[#ffe5e5] text-[#7f1d1d]",
};

const eventStyles: Record<string, string> = {
  queued: "border-[#b7c3cc] bg-[#f4f6f7] text-[#52616b]",
  running: "border-[#8ab6c5] bg-[#edf7fa] text-[#236276]",
  succeeded: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
  no_card: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
  warning: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  failed: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
};

const reviewStyles: Record<FindingReviewStatus, string> = {
  open: "border-[#b7c3cc] bg-[#f4f6f7] text-[#52616b]",
  confirmed: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  accepted: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
  false_positive: "border-[#c9b6d8] bg-[#f7f1fb] text-[#68437d]",
  resolved: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
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

type FindingReviewDraft = {
  review_status: FindingReviewStatus;
  analyst_notes: string;
};

const cardTypeOptions = [
  "EM4100",
  "TK4100",
  "T5577",
  "HID Prox",
  "MIFARE Classic 1K",
  "NTAG213",
  "NTAG215",
  "NTAG216",
];

const traceProtocolOptions: Array<{ value: TraceProtocol; label: string }> = [
  { value: "14a", label: "ISO 14443-A" },
  { value: "mf", label: "MIFARE Classic" },
  { value: "des", label: "MIFARE DESFire" },
  { value: "7816", label: "ISO 7816-4" },
  { value: "15", label: "ISO 15693" },
  { value: "iclass", label: "iCLASS" },
];

function traceSummary(trace: TransactionTrace): TransactionTraceSummary {
  return {
    id: trace.id,
    session_id: trace.session_id,
    name: trace.name,
    protocol: trace.protocol,
    source: trace.source,
    status: trace.status,
    risk_level: trace.risk_level,
    confidence: trace.confidence,
    frame_count: trace.frame_count,
    reader_frame_count: trace.reader_frame_count,
    card_frame_count: trace.card_frame_count,
    apdu_count: trace.apdu_count,
    raw_sha256: trace.raw_sha256,
    summary_json: trace.summary_json,
    created_at: trace.created_at,
  };
}

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function resolveSessionId(value: string | string[] | undefined) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  const parsedValue = Number(rawValue);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

function withMaskedEmvEvidence(card: DetectedCard): Record<string, unknown> {
  const normalized = card.normalized_data_json;
  const rawInspectionOutputs = card.raw_output_json.inspection_outputs;
  if (
    !rawInspectionOutputs ||
    typeof rawInspectionOutputs !== "object" ||
    Array.isArray(rawInspectionOutputs)
  ) {
    return normalized;
  }

  const emvReaderOutput = (rawInspectionOutputs as Record<string, unknown>)
    .hf_emv_reader;
  if (typeof emvReaderOutput !== "string") {
    return normalized;
  }

  const panLastFour = emvReaderOutput.match(
    /\[REDACTED:PAN:LAST4-(\d{4})\]/i,
  );
  const trackDataPresent = /\[REDACTED:TRACK_DATA\]/i.test(emvReaderOutput);
  if (!panLastFour && !trackDataPresent) {
    return normalized;
  }

  const inspectionValue = normalized.inspection;
  const inspection =
    inspectionValue && typeof inspectionValue === "object" && !Array.isArray(inspectionValue)
      ? (inspectionValue as Record<string, unknown>)
      : {};
  const combinedValue = inspection.combined_fields;
  const combinedFields =
    combinedValue && typeof combinedValue === "object" && !Array.isArray(combinedValue)
      ? (combinedValue as Record<string, unknown>)
      : {};

  return {
    ...normalized,
    inspection: {
      ...inspection,
      combined_fields: {
        ...combinedFields,
        ...(panLastFour && combinedFields.pan === undefined
          ? { pan: `•••• ${panLastFour[1]}` }
          : {}),
        ...(trackDataPresent && combinedFields.track_2_equivalent === undefined
          ? { track_2_equivalent: "Present (redacted)" }
          : {}),
      },
    },
  };
}

export default function SessionDetailsPage() {
  const params = useParams<{ sessionId?: string | string[] }>();
  const router = useRouter();
  const sessionId = resolveSessionId(params.sessionId);

  const [session, setSession] = useState<ScanSession | null>(null);
  const [cards, setCards] = useState<DetectedCard[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [assessments, setAssessments] = useState<AssessmentRun[]>([]);
  const [operatorCommands, setOperatorCommands] = useState<OperatorCommand[]>([]);
  const [operatorRecipes, setOperatorRecipes] = useState<OperatorRecipe[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilityRegistry | null>(null);
  const [guidance, setGuidance] = useState<GuidedEvidence | null>(null);
  const [assurancePolicies, setAssurancePolicies] = useState<AssurancePolicy[]>([]);
  const [sessionAssurance, setSessionAssurance] = useState<SessionAssurance | null>(null);
  const [selectedAssurancePolicy, setSelectedAssurancePolicy] =
    useState("university-standard");
  const [transactionTraces, setTransactionTraces] = useState<
    TransactionTraceSummary[]
  >([]);
  const [selectedTrace, setSelectedTrace] = useState<TransactionTrace | null>(null);
  const [traceName, setTraceName] = useState("Reader transaction");
  const [traceProtocol, setTraceProtocol] = useState<TraceProtocol>("14a");
  const [traceRawOutput, setTraceRawOutput] = useState("");
  const [selectedRecipe, setSelectedRecipe] = useState("");
  const [lastRecipeRun, setLastRecipeRun] = useState<OperatorRecipeRun | null>(null);
  const [commandInput, setCommandInput] = useState("hw version");
  const [assessmentBand, setAssessmentBand] = useState<"hf" | "lf" | "emv">("hf");
  const [reviewDrafts, setReviewDrafts] = useState<
    Record<number, FindingReviewDraft>
  >({});
  const [technology, setTechnology] = useState("");
  const [cardType, setCardType] = useState("");
  const [source, setSource] = useState("");
  const [dataset, setDataset] = useState("");
  const [fileType, setFileType] = useState("");
  const [uidFilter, setUidFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<
    "overview" | "guidance" | "acquisition" | "analysis" | "evidence"
  >("overview");

  const refreshSession = useCallback(async () => {
    if (sessionId === null) {
      setError("Invalid session id.");
      setIsLoading(false);
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      const [
        sessionData,
        cardData,
        findingData,
        assessmentData,
        commandData,
        recipeData,
        policyData,
        assuranceData,
        traceData,
        capabilityData,
        guidanceData,
      ] =
        await Promise.all([
          getSession(sessionId),
          listSessionCards(sessionId),
          listSessionFindings(sessionId),
          listSessionAssessments(sessionId),
          listSessionOperatorCommands(sessionId),
          listSessionOperatorRecipes(sessionId),
          listAssurancePolicies(),
          getSessionAssurance(sessionId, selectedAssurancePolicy),
          listSessionTransactionTraces(sessionId),
          getSessionCapabilities(sessionId),
          getSessionEvidenceGuidance(sessionId, selectedAssurancePolicy),
        ]);
      setSession(sessionData);
      setCards(cardData);
      setFindings(findingData);
      setAssessments(assessmentData);
      setOperatorCommands(commandData);
      setOperatorRecipes(recipeData);
      setAssurancePolicies(policyData);
      setSessionAssurance(assuranceData);
      setTransactionTraces(traceData);
      setCapabilities(capabilityData);
      setGuidance(guidanceData);
      setSelectedTrace(
        traceData[0]
          ? await getSessionTransactionTrace(sessionId, traceData[0].id)
          : null,
      );
      setSelectedRecipe((current) => current || recipeData[0]?.key || "");
      setReviewDrafts((current) => {
        const next: Record<number, FindingReviewDraft> = {};
        for (const finding of findingData) {
          next[finding.id] = current[finding.id] ?? {
            review_status: finding.review_status,
            analyst_notes: finding.analyst_notes ?? "",
          };
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load session.");
    } finally {
      setIsLoading(false);
    }
  }, [selectedAssurancePolicy, sessionId]);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  const hasActiveAssessment = assessments.some((assessment) =>
    ["queued", "running"].includes(assessment.status),
  );

  useEffect(() => {
    if (!hasActiveAssessment || sessionId === null) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const assessmentData = await listSessionAssessments(sessionId);
        setAssessments(assessmentData);
        if (!assessmentData.some((item) => ["queued", "running"].includes(item.status))) {
          await refreshSession();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to refresh assessment progress.");
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [hasActiveAssessment, refreshSession, sessionId]);

  async function runAction(
    actionKey: string,
    action: () => Promise<ScanSession | DetectedCard | void>,
  ) {
    setActiveAction(actionKey);
    setError(null);
    try {
      await action();
      await refreshSession();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update session.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleDelete() {
    if (sessionId === null) {
      return;
    }

    setActiveAction("delete");
    setError(null);
    try {
      await deleteSession(sessionId);
      router.push("/sessions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete session.");
      setActiveAction(null);
    }
  }

  async function handleAutomatedAssessment() {
    if (sessionId === null) {
      return;
    }

    setActiveAction("assessment");
    setError(null);
    try {
      const assessment = await startAutomatedAssessment(sessionId, assessmentBand);
      setAssessments((current) => [
        assessment,
        ...current.filter((item) => item.id !== assessment.id),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start automated assessment.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleOperatorCommand() {
    if (sessionId === null || !commandInput.trim()) {
      return;
    }

    setActiveAction("operator-command");
    setError(null);
    try {
      const result = await runSessionOperatorCommand(
        sessionId,
        commandInput,
      );
      setOperatorCommands((current) => [
        result,
        ...current.filter((item) => item.id !== result.id),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run command.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleOperatorRecipe() {
    if (sessionId === null || !selectedRecipe) {
      return;
    }

    setActiveAction("operator-recipe");
    setError(null);
    try {
      const result = await runSessionOperatorRecipe(sessionId, selectedRecipe);
      setLastRecipeRun(result);
      setOperatorCommands((current) => [
        ...result.results.slice().reverse(),
        ...current.filter(
          (item) => !result.results.some((resultItem) => resultItem.id === item.id),
        ),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run recipe.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleGuidedRecipe(
    recipeKey: string,
    recommendationId: string,
  ) {
    if (sessionId === null) {
      return;
    }

    setActiveAction(`guidance-${recommendationId}`);
    setError(null);
    try {
      const result = await runSessionOperatorRecipe(sessionId, recipeKey);
      setLastRecipeRun(result);
      await refreshSession();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run guided recipe.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleFindingReview(findingId: number) {
    const draft = reviewDrafts[findingId];
    if (!draft) {
      return;
    }

    setActiveAction(`finding-${findingId}`);
    setError(null);
    try {
      const updated = await updateFinding(findingId, {
        review_status: draft.review_status,
        analyst_notes: draft.analyst_notes,
      });
      setFindings((current) =>
        current.map((finding) =>
          finding.id === updated.id ? updated : finding,
        ),
      );
      setReviewDrafts((current) => ({
        ...current,
        [findingId]: {
          review_status: updated.review_status,
          analyst_notes: updated.analyst_notes ?? "",
        },
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to review finding.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleImportedTrace() {
    if (sessionId === null || !traceRawOutput.trim()) {
      return;
    }
    setActiveAction("trace-import");
    setError(null);
    try {
      const result = await analyzeSessionTransactionTrace(sessionId, {
        name: traceName.trim() || "Imported reader transaction",
        protocol: traceProtocol,
        raw_output: traceRawOutput,
      });
      setSelectedTrace(result);
      setTransactionTraces((current) => [
        traceSummary(result),
        ...current.filter((item) => item.id !== result.id),
      ]);
      setTraceRawOutput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to analyze trace output.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleDeviceTraceBuffer() {
    if (sessionId === null) {
      return;
    }
    setActiveAction("trace-buffer");
    setError(null);
    try {
      const result = await analyzeSessionDeviceTraceBuffer(sessionId, {
        name: traceName.trim() || "Proxmark trace buffer",
        protocol: traceProtocol,
      });
      setSelectedTrace(result);
      setTransactionTraces((current) => [
        traceSummary(result),
        ...current.filter((item) => item.id !== result.id),
      ]);
      setOperatorCommands(await listSessionOperatorCommands(sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to retrieve trace buffer.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleSelectTrace(traceId: number) {
    if (sessionId === null || selectedTrace?.id === traceId) {
      return;
    }
    setActiveAction(`trace-${traceId}`);
    setError(null);
    try {
      setSelectedTrace(await getSessionTransactionTrace(sessionId, traceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load trace analysis.");
    } finally {
      setActiveAction(null);
    }
  }

  const latestCard = cards[0];
  const latestCardEvidence = latestCard ? withMaskedEmvEvidence(latestCard) : null;
  const latestAssessment = assessments[0];
  const highRiskCount = findings.filter((finding) =>
    ["high", "critical"].includes(finding.risk_level),
  ).length;
  const cardLabelById = new Map(
    cards.map((card) => [card.id, `${card.card_type} ${card.uid}`] as const),
  );
  const selectedRecipeDefinition = operatorRecipes.find(
    (recipe) => recipe.key === selectedRecipe,
  );
  const safeOperatorCommands = capabilities?.commands.map((item) => item.command) ?? [];

  return (
    <main className="deep-workspace">
      <section className="page-container">
        <header className="page-header">
          <div>
            <p className="text-sm font-semibold uppercase text-[#2f6f73]">
              Operator panel
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-[#17202a] sm:text-4xl">
              {session?.session_name ?? "Session Details"}
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {session ? (
              <Link
                href={`/sessions/${session.id}/measurements`}
                className="inline-flex items-center justify-center rounded-md bg-[#2f6f73] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#255b5f] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
              >
                Research Measurements
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

        <nav className="workspace-tabs" aria-label="Operator workspace views">
          {[
            { key: "overview", label: "Overview", icon: Activity },
            { key: "guidance", label: "Guided Evidence", icon: Compass },
            { key: "acquisition", label: "Acquisition", icon: RadioTower },
            { key: "analysis", label: "Analysis", icon: BarChart3 },
            { key: "evidence", label: "Evidence", icon: Database },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                type="button"
                className={`workspace-tab ${activeWorkspace === item.key ? "workspace-tab-active" : ""}`}
                onClick={() => setActiveWorkspace(item.key as typeof activeWorkspace)}
                aria-pressed={activeWorkspace === item.key}
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
            Loading session...
          </div>
        ) : session ? (
          <div className="grid gap-5 py-8 lg:grid-cols-[360px_minmax(0,1fr)]">
            <aside className="space-y-5">
              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-lg font-semibold text-[#17202a]">
                    Session
                  </h2>
                  <span
                    className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                      statusStyles[session.status] ??
                      "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                    }`}
                  >
                    {session.status}
                  </span>
                </div>
                <dl className="mt-5 space-y-4 text-sm">
                  <div>
                    <dt className="font-medium text-[#52616b]">Description</dt>
                    <dd className="mt-1 text-[#17202a]">
                      {session.description || "-"}
                    </dd>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="font-medium text-[#52616b]">Mode</dt>
                      <dd className="mt-1 capitalize text-[#17202a]">
                        {session.mode}
                      </dd>
                    </div>
                    <div>
                      <dt className="font-medium text-[#52616b]">
                        Environment
                      </dt>
                      <dd className="mt-1 capitalize text-[#17202a]">
                        {session.environment}
                      </dd>
                    </div>
                  </div>
                  <div>
                    <dt className="font-medium text-[#52616b]">Started</dt>
                    <dd className="mt-1 text-[#17202a]">
                      {formatDate(session.started_at)}
                    </dd>
                  </div>
                  <div>
                    <dt className="font-medium text-[#52616b]">Ended</dt>
                    <dd className="mt-1 text-[#17202a]">
                      {formatDate(session.ended_at)}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Operator Controls
                </h2>
                <div className="mt-5 grid gap-3">
                  <button
                    type="button"
                    disabled={
                      session.status !== "created" || activeAction === "start"
                    }
                    onClick={() =>
                      void runAction("start", () => startSession(session.id))
                    }
                    className="rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-4 py-2.5 text-sm font-semibold text-[#1f6f61] transition hover:bg-[#d8eee9] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                  >
                    Start Session
                  </button>
                  <button
                    type="button"
                    disabled={
                      session.status !== "running" || activeAction === "stop"
                    }
                    onClick={() =>
                      void runAction("stop", () => stopSession(session.id))
                    }
                    className="rounded-md border border-[#b8c4d6] bg-[#eef3fa] px-4 py-2.5 text-sm font-semibold text-[#315a8a] transition hover:bg-[#e1ebf8] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                  >
                    Stop Session
                  </button>
                  <button
                    type="button"
                    disabled={activeAction === "delete"}
                    onClick={() => void handleDelete()}
                    className="rounded-md border border-[#e6b8b8] bg-[#fff4f4] px-4 py-2.5 text-sm font-semibold text-[#9b2c2c] transition hover:bg-[#ffe8e8] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                  >
                    Delete Session
                  </button>
                </div>
              </section>

              <section
                className={`rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm ${
                  session.mode === "simulator" ? "" : "hidden"
                }`}
              >
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Simulated Scan
                </h2>
                <label className="mt-5 block text-sm font-medium text-[#36454f]">
                  Technology
                  <select
                    value={technology}
                    onChange={(event) => setTechnology(event.target.value)}
                    className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                  >
                    <option value="">Any</option>
                    <option value="LF RFID">LF RFID</option>
                    <option value="HF/NFC">HF/NFC</option>
                  </select>
                </label>
                <label className="mt-4 block text-sm font-medium text-[#36454f]">
                  Card type
                  <select
                    value={cardType}
                    onChange={(event) => setCardType(event.target.value)}
                    className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                  >
                    <option value="">Any</option>
                    {cardTypeOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="mt-4 block text-sm font-medium text-[#36454f]">
                  Source
                  <select
                    value={source}
                    onChange={(event) => setSource(event.target.value)}
                    className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                  >
                    <option value="">Any</option>
                    <option value="simulator">Simulator</option>
                    <option value="flipper-import">Flipper import</option>
                  </select>
                </label>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="block text-sm font-medium text-[#36454f]">
                    File type
                    <select
                      value={fileType}
                      onChange={(event) => setFileType(event.target.value)}
                      className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                    >
                      <option value="">Any</option>
                      <option value="nfc">NFC</option>
                      <option value="rfid">RFID</option>
                    </select>
                  </label>
                  <label className="block text-sm font-medium text-[#36454f]">
                    Dataset
                    <input
                      value={dataset}
                      onChange={(event) => setDataset(event.target.value)}
                      placeholder="uberguidoz-flipper"
                      className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                    />
                  </label>
                </div>
                <label className="mt-4 block text-sm font-medium text-[#36454f]">
                  UID
                  <input
                    value={uidFilter}
                    onChange={(event) => setUidFilter(event.target.value)}
                    placeholder="04:A1:B2:C3:D4:E5:80"
                    className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                  />
                </label>
                <button
                  type="button"
                  disabled={session.status !== "running" || activeAction === "scan"}
                  onClick={() =>
                    void runAction("scan", () =>
                      simulateSessionScan(session.id, {
                        technology: technology || null,
                        card_type: cardType || null,
                        source: source || null,
                        dataset: dataset.trim() || null,
                        file_type: fileType || null,
                        uid: uidFilter.trim() || null,
                      }),
                    )
                  }
                  className="mt-5 w-full rounded-md bg-[#2f6f73] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#255b5f] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#8daaad]"
                >
                  Run Simulated Scan
                </button>
              </section>
            </aside>

            <section className="min-w-0 space-y-5">
              <div className="grid gap-4 sm:grid-cols-3">
                <article className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                  <p className="text-sm font-medium text-[#52616b]">
                    Cards Detected
                  </p>
                  <p className="mt-4 text-3xl font-semibold text-[#17202a]">
                    {cards.length}
                  </p>
                </article>
                <article className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                  <p className="text-sm font-medium text-[#52616b]">
                    High Risk Findings
                  </p>
                  <p className="mt-4 text-3xl font-semibold text-[#17202a]">
                    {highRiskCount}
                  </p>
                </article>
                <article className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                  <p className="text-sm font-medium text-[#52616b]">
                    Latest Card
                  </p>
                  {latestCard ? (
                    <button
                      type="button"
                      onClick={() => router.push(`/cards/${latestCard.id}`)}
                      className="mt-4 block truncate text-lg font-semibold text-[#17202a] underline-offset-4 transition hover:text-[#2f6f73] hover:underline"
                    >
                      {latestCard.card_type}
                    </button>
                  ) : (
                    <p className="mt-4 truncate text-lg font-semibold text-[#17202a]">
                      -
                    </p>
                  )}
                </article>
              </div>

              {activeWorkspace === "guidance" && guidance ? (
                <GuidedEvidencePanel
                  guidance={guidance}
                  activeAction={activeAction}
                  onRunRecipe={handleGuidedRecipe}
                  onOpenWorkspace={(workspace) => {
                    if (["overview", "acquisition", "analysis", "evidence"].includes(workspace)) {
                      setActiveWorkspace(
                        workspace as "overview" | "acquisition" | "analysis" | "evidence",
                      );
                    }
                  }}
                />
              ) : null}

              <section className={`rounded-lg border border-[#cbd6dc] bg-white shadow-sm ${["overview", "acquisition"].includes(activeWorkspace) ? "" : "hidden"}`}>
                <div className="flex flex-col gap-4 border-b border-[#edf0f2] p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Automated Reconnaissance
                      </h2>
                      <span className="rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2 py-1 text-xs font-semibold text-[#1f6f61]">
                        Read-only
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[#52616b]">
                      Hardware preflight and protocol-specific evidence acquisition.
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 sm:items-end">
                    <fieldset>
                      <legend className="sr-only">Assessment frequency band</legend>
                      <div className="inline-flex rounded-md border border-[#b7c3cc] bg-[#f4f6f7] p-1" role="group">
                        {([
                          ["hf", "HF 13.56 MHz"],
                          ["lf", "LF 125 kHz"],
                          ["emv", "Advanced EMV"],
                        ] as const).map(([value, label]) => (
                          <button
                            key={value}
                            type="button"
                            aria-pressed={assessmentBand === value}
                            disabled={hasActiveAssessment || activeAction === "assessment"}
                            onClick={() => setAssessmentBand(value)}
                            className={`min-h-9 rounded px-3 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60 ${
                              assessmentBand === value
                                ? "bg-white text-[#17202a] shadow-sm"
                                : "text-[#52616b] hover:text-[#17202a]"
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </fieldset>
                    <button
                      type="button"
                      disabled={
                        session.mode !== "proxmark" ||
                        session.status !== "running" ||
                        hasActiveAssessment ||
                        activeAction === "assessment"
                      }
                      onClick={() => void handleAutomatedAssessment()}
                      className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-md bg-[#2f6f73] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#255b5f] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#8daaad]"
                    >
                      {hasActiveAssessment
                        ? "Assessment Running"
                        : assessmentBand === "emv"
                          ? "Run Advanced EMV"
                          : `Run ${assessmentBand.toUpperCase()} Assessment`}
                    </button>
                  </div>
                </div>

                <div className="border-b border-[#edf0f2] bg-[#f7f9fa] px-5 py-3 text-sm text-[#52616b]">
                  {assessmentBand === "emv"
                    ? "Present one authorized contactless payment test card. PASS-PAC will run PPSE discovery, AID search, a bounded application read, and redacted ISO 7816 history. PAN, track data, and cardholder name are never retained."
                    : `Place one ${assessmentBand.toUpperCase()} test card on the matching Proxmark antenna before starting. Wait for the run to finish before moving the card or starting another command.`}
                </div>

                {session.mode !== "proxmark" ? (
                  <div className="p-5 text-sm text-[#52616b]">
                    Create a Proxmark session to run live automated reconnaissance. Simulator sessions remain dataset-only.
                  </div>
                ) : latestAssessment ? (
                  <div className="p-5">
                    <div className="grid gap-3 border-b border-[#edf0f2] pb-5 sm:grid-cols-4">
                      <div>
                        <p className="text-xs font-semibold uppercase text-[#6b7780]">Run</p>
                        <p className="mt-1 font-semibold text-[#17202a]">#{latestAssessment.id}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase text-[#6b7780]">Status</p>
                        <p className="mt-1 capitalize font-semibold text-[#17202a]">{latestAssessment.status}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase text-[#6b7780]">Credentials</p>
                        <p className="mt-1 font-semibold text-[#17202a]">{latestAssessment.detected_card_count}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase text-[#6b7780]">Started</p>
                        <p className="mt-1 text-sm font-medium text-[#17202a]">{formatDate(latestAssessment.started_at)}</p>
                      </div>
                    </div>

                    <ol className="mt-5 space-y-0">
                      {latestAssessment.events.map((event, index) => (
                        <li key={event.id} className="grid grid-cols-[24px_minmax(0,1fr)] gap-3">
                          <div className="flex flex-col items-center">
                            <span
                              className={`mt-1 h-3 w-3 rounded-full border-2 ${
                                event.status === "failed"
                                  ? "border-[#b94b4b] bg-[#fff0f0]"
                                  : event.status === "warning"
                                    ? "border-[#b59820] bg-[#fff8dc]"
                                    : event.status === "running"
                                      ? "border-[#31809a] bg-[#edf7fa]"
                                      : "border-[#3b8878] bg-[#e8f5f2]"
                              }`}
                            />
                            {index < latestAssessment.events.length - 1 ? (
                              <span className="min-h-10 w-px flex-1 bg-[#d8dde3]" />
                            ) : null}
                          </div>
                          <div className="pb-5">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-[#17202a]">{event.title}</p>
                              <span
                                className={`rounded-md border px-2 py-0.5 text-xs font-semibold capitalize ${
                                  eventStyles[event.status] ?? eventStyles.queued
                                }`}
                              >
                                {event.status.replace("_", " ")}
                              </span>
                              {event.command ? (
                                <code className="text-xs text-[#52616b]">{event.command}</code>
                              ) : null}
                            </div>
                            <p className="mt-1 text-sm text-[#52616b]">{event.message}</p>
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : (
                  <div className="p-5 text-sm text-[#52616b]">
                    No automated assessment has been run for this session.
                  </div>
                )}
              </section>

              <section className={`rounded-lg border border-[#cbd6dc] bg-white shadow-sm ${activeWorkspace === "analysis" ? "" : "hidden"}`}>
                <div className="flex flex-col gap-3 border-b border-[#edf0f2] p-5 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Reader Transaction Analyzer
                      </h2>
                      <span className="rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2 py-1 text-xs font-semibold text-[#1f6f61]">
                        Passive evidence
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[#52616b]">
                      Authentication sequence, APDU, and reader-card frame analysis.
                    </p>
                  </div>
                  <span className="w-fit rounded-md border border-[#b8c4d6] bg-[#eef3fa] px-2.5 py-1 text-xs font-semibold text-[#315a8a]">
                    {transactionTraces.length} stored
                  </span>
                </div>

                <div className="grid gap-4 border-b border-[#edf0f2] p-5 lg:grid-cols-[minmax(0,1fr)_220px]">
                  <label className="block text-sm font-medium text-[#36454f]">
                    Trace name
                    <input
                      value={traceName}
                      onChange={(event) => setTraceName(event.target.value)}
                      maxLength={160}
                      className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                    />
                  </label>
                  <label className="block text-sm font-medium text-[#36454f]">
                    Protocol
                    <select
                      value={traceProtocol}
                      onChange={(event) => setTraceProtocol(event.target.value as TraceProtocol)}
                      className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                    >
                      {traceProtocolOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm font-medium text-[#36454f] lg:col-span-2">
                    Proxmark trace output
                    <textarea
                      value={traceRawOutput}
                      onChange={(event) => setTraceRawOutput(event.target.value)}
                      rows={7}
                      placeholder="Paste complete trace list output"
                      className="mt-2 w-full resize-y rounded-md border border-[#b7c3cc] bg-[#111827] px-3 py-2 font-mono text-xs leading-6 text-[#f8fafc] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                    />
                  </label>
                  <div className="flex flex-col gap-2 sm:flex-row lg:col-span-2">
                    <button
                      type="button"
                      disabled={!traceRawOutput.trim() || activeAction === "trace-import"}
                      onClick={() => void handleImportedTrace()}
                      className="inline-flex min-h-10 items-center justify-center rounded-md bg-[#2f6f73] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#255b5f] disabled:cursor-not-allowed disabled:bg-[#8daaad]"
                    >
                      {activeAction === "trace-import" ? "Analyzing..." : "Analyze Imported Trace"}
                    </button>
                    <button
                      type="button"
                      disabled={
                        session.mode !== "proxmark" ||
                        session.status !== "running" ||
                        activeAction === "trace-buffer"
                      }
                      onClick={() => void handleDeviceTraceBuffer()}
                      className="inline-flex min-h-10 items-center justify-center rounded-md border border-[#8ab6c5] bg-[#edf7fa] px-4 py-2 text-sm font-semibold text-[#236276] transition hover:bg-[#dff1f5] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                    >
                      {activeAction === "trace-buffer" ? "Reading..." : "Read Device Buffer"}
                    </button>
                  </div>
                </div>

                <div className="grid min-w-0 lg:grid-cols-[260px_minmax(0,1fr)]">
                  <div className="border-b border-[#edf0f2] lg:border-b-0 lg:border-r">
                    <div className="border-b border-[#edf0f2] px-4 py-3 text-xs font-semibold uppercase text-[#6b7780]">
                      Analyses
                    </div>
                    {transactionTraces.length === 0 ? (
                      <p className="p-4 text-sm text-[#6b7780]">No transaction traces stored.</p>
                    ) : (
                      <div className="divide-y divide-[#edf0f2]">
                        {transactionTraces.map((trace) => (
                          <button
                            key={trace.id}
                            type="button"
                            onClick={() => void handleSelectTrace(trace.id)}
                            className={`block w-full px-4 py-4 text-left transition hover:bg-[#f7f9fa] ${
                              selectedTrace?.id === trace.id ? "bg-[#edf7f6]" : "bg-white"
                            }`}
                          >
                            <span className="block truncate text-sm font-semibold text-[#17202a]">
                              {trace.name}
                            </span>
                            <span className="mt-1 block text-xs text-[#6b7780]">
                              {traceProtocolOptions.find((item) => item.value === trace.protocol)?.label ?? trace.protocol}
                              {" / "}{trace.frame_count} frames
                            </span>
                            <span className={`mt-2 inline-flex rounded-md border px-2 py-0.5 text-xs font-semibold capitalize ${
                              riskStyles[trace.risk_level] ?? riskStyles.informational
                            }`}>
                              {trace.risk_level}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="min-w-0">
                    {selectedTrace ? (
                      <div>
                        <div className="border-b border-[#edf0f2] p-5">
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <h3 className="font-semibold text-[#17202a]">{selectedTrace.name}</h3>
                              <p className="mt-1 break-all font-mono text-xs text-[#6b7780]">
                                SHA-256 {selectedTrace.raw_sha256}
                              </p>
                            </div>
                            <span className={`w-fit rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                              riskStyles[selectedTrace.risk_level] ?? riskStyles.informational
                            }`}>
                              {selectedTrace.risk_level} / {selectedTrace.confidence}
                            </span>
                          </div>
                          <p className="mt-4 text-sm leading-6 text-[#36454f]">
                            {String(selectedTrace.summary_json.summary ?? "Trace analysis complete.")}
                          </p>
                          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                            <div>
                              <p className="text-xs font-semibold uppercase text-[#6b7780]">Frames</p>
                              <p className="mt-1 text-xl font-semibold text-[#17202a]">{selectedTrace.frame_count}</p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold uppercase text-[#6b7780]">Reader</p>
                              <p className="mt-1 text-xl font-semibold text-[#17202a]">{selectedTrace.reader_frame_count}</p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold uppercase text-[#6b7780]">Card</p>
                              <p className="mt-1 text-xl font-semibold text-[#17202a]">{selectedTrace.card_frame_count}</p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold uppercase text-[#6b7780]">APDUs</p>
                              <p className="mt-1 text-xl font-semibold text-[#17202a]">{selectedTrace.apdu_count}</p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold uppercase text-[#6b7780]">Authentication</p>
                              <p className="mt-1 text-sm font-semibold capitalize text-[#17202a]">
                                {String(selectedTrace.summary_json.authentication_state ?? "inconclusive").replace("_", " ")}
                              </p>
                            </div>
                          </div>
                        </div>

                        <div className="border-b border-[#edf0f2] p-5">
                          <h3 className="text-sm font-semibold text-[#17202a]">Trace findings</h3>
                          {selectedTrace.findings_json.length === 0 ? (
                            <p className="mt-3 text-sm text-[#6b7780]">No trace findings generated.</p>
                          ) : (
                            <div className="mt-3 divide-y divide-[#edf0f2] border-y border-[#edf0f2]">
                              {selectedTrace.findings_json.map((finding) => (
                                <article key={finding.rule_id} className="py-4">
                                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                    <div>
                                      <h4 className="font-semibold text-[#17202a]">{finding.title}</h4>
                                      <p className="mt-1 text-sm leading-6 text-[#52616b]">{finding.description}</p>
                                    </div>
                                    <span className={`w-fit shrink-0 rounded-md border px-2 py-1 text-xs font-semibold capitalize ${
                                      riskStyles[finding.risk_level] ?? riskStyles.informational
                                    }`}>
                                      {finding.risk_level} / {finding.confidence}
                                    </span>
                                  </div>
                                  <p className="mt-3 text-sm text-[#36454f]">
                                    <span className="font-semibold">Action:</span> {finding.recommendation}
                                  </p>
                                  {finding.frame_sequences.length > 0 ? (
                                    <p className="mt-2 font-mono text-xs text-[#6b7780]">
                                      Frames {finding.frame_sequences.join(", ")}
                                    </p>
                                  ) : null}
                                </article>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="border-b border-[#edf0f2] p-5">
                          <h3 className="text-sm font-semibold text-[#17202a]">Frame timeline</h3>
                          <div className="mt-3 overflow-x-auto rounded-md border border-[#d8dde3]">
                            <table className="w-full min-w-[850px] border-collapse text-left text-xs">
                              <thead className="bg-[#fafbfc] uppercase text-[#52616b]">
                                <tr>
                                  <th className="px-3 py-2 font-semibold">#</th>
                                  <th className="px-3 py-2 font-semibold">Direction</th>
                                  <th className="px-3 py-2 font-semibold">Timing</th>
                                  <th className="px-3 py-2 font-semibold">Data</th>
                                  <th className="px-3 py-2 font-semibold">Interpretation</th>
                                  <th className="px-3 py-2 font-semibold">CRC</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-[#edf0f2]">
                                {selectedTrace.frames_json.slice(0, 200).map((frame) => (
                                  <tr key={frame.sequence}>
                                    <td className="px-3 py-3 font-semibold text-[#17202a]">{frame.sequence}</td>
                                    <td className="px-3 py-3">
                                      <span className={`rounded-md border px-2 py-1 font-semibold ${
                                        frame.source === "reader"
                                          ? "border-[#8ab6c5] bg-[#edf7fa] text-[#236276]"
                                          : "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]"
                                      }`}>
                                        {frame.source === "reader" ? "Reader -> Card" : "Card -> Reader"}
                                      </span>
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-3 font-mono text-[#52616b]">
                                      {frame.start} - {frame.end}
                                    </td>
                                    <td className="max-w-[360px] break-all px-3 py-3 font-mono text-[#17202a]">
                                      {frame.data_hex}
                                    </td>
                                    <td className="px-3 py-3 text-[#36454f]">
                                      {frame.command ?? frame.annotation ?? "-"}
                                    </td>
                                    <td className="px-3 py-3 text-[#52616b]">{frame.crc ?? "-"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          {selectedTrace.frames_json.length > 200 ? (
                            <p className="mt-2 text-xs text-[#6b7780]">Timeline limited to the first 200 frames.</p>
                          ) : null}
                        </div>

                        <details className="p-5">
                          <summary className="cursor-pointer text-sm font-semibold text-[#17202a]">
                            Raw trace evidence
                          </summary>
                          <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#e2e8f0]">
                            {selectedTrace.raw_output}
                          </pre>
                        </details>
                      </div>
                    ) : (
                      <p className="p-5 text-sm text-[#6b7780]">Select or create a trace analysis.</p>
                    )}
                  </div>
                </div>
              </section>

              <section className={`rounded-lg border border-[#cbd6dc] bg-white shadow-sm ${activeWorkspace === "acquisition" ? "" : "hidden"}`}>
                <div className="flex flex-col gap-3 border-b border-[#edf0f2] p-5 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-[#17202a]">
                      Operator Console
                    </h2>
                    <p className="mt-1 text-sm text-[#52616b]">
                      COM8 / Proxmark3 client
                    </p>
                  </div>
                  <span className="w-fit rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-2.5 py-1 text-xs font-semibold text-[#1f6f61]">
                    Read-only allowlist
                  </span>
                </div>

                {session.mode === "proxmark" ? (
                  <div className="p-5">
                    <div className="mb-5 border-b border-[#edf0f2] pb-5">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                        <label className="min-w-0 flex-1 text-sm font-medium text-[#36454f]">
                          Assessment Recipe
                          <select
                            value={selectedRecipe}
                            onChange={(event) => setSelectedRecipe(event.target.value)}
                            className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2.5 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                          >
                            {operatorRecipes.map((recipe) => (
                              <option key={recipe.key} value={recipe.key}>
                                {recipe.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          type="button"
                          disabled={
                            session.status !== "running" ||
                            activeAction === "operator-recipe" ||
                            !selectedRecipe
                          }
                          onClick={() => void handleOperatorRecipe()}
                          className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-md border border-[#315a8a] bg-[#eef3fa] px-5 py-2.5 text-sm font-semibold text-[#315a8a] transition hover:bg-[#e1ebf8] focus:outline-none focus:ring-2 focus:ring-[#315a8a] focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                        >
                          {activeAction === "operator-recipe"
                            ? "Running Recipe..."
                            : "Run Recipe"}
                        </button>
                      </div>
                      {selectedRecipeDefinition ? (
                        <div className="mt-3">
                          <p className="text-sm text-[#52616b]">
                            {selectedRecipeDefinition.description}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {selectedRecipeDefinition.commands.map((command) => (
                              <code
                                key={`${selectedRecipeDefinition.key}-${command}`}
                                className="rounded-md border border-[#d8dde3] bg-[#fafbfc] px-2 py-1 text-xs text-[#52616b]"
                              >
                                {command}
                              </code>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {lastRecipeRun ? (
                        <p className="mt-3 text-xs font-semibold text-[#52616b]">
                          {lastRecipeRun.recipe.name}: {lastRecipeRun.successful_count}/
                          {lastRecipeRun.command_count} commands succeeded
                        </p>
                      ) : null}
                    </div>

                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        void handleOperatorCommand();
                      }}
                      className="flex flex-col gap-3 sm:flex-row sm:items-end"
                    >
                      <label className="min-w-0 flex-1 text-sm font-medium text-[#36454f]">
                        Command
                        <input
                          list="safe-proxmark-commands"
                          value={commandInput}
                          onChange={(event) => setCommandInput(event.target.value)}
                          spellCheck={false}
                          autoComplete="off"
                          className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-[#111827] px-3 py-2.5 font-mono text-sm text-[#f8fafc] outline-none transition placeholder:text-[#94a3b8] focus:border-[#69a9a0] focus:ring-2 focus:ring-[#cfe7e5]"
                        />
                        <datalist id="safe-proxmark-commands">
                          {safeOperatorCommands.map((command) => (
                            <option key={command} value={command} />
                          ))}
                        </datalist>
                      </label>
                      <button
                        type="submit"
                        disabled={
                          session.status !== "running" ||
                          activeAction === "operator-command" ||
                          !commandInput.trim()
                        }
                        className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-md bg-[#2f6f73] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#255b5f] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#8daaad]"
                      >
                        {activeAction === "operator-command" ? "Running..." : "Run Command"}
                      </button>
                    </form>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {safeOperatorCommands.slice(0, 5).map((command) => (
                        <button
                          key={command}
                          type="button"
                          onClick={() => setCommandInput(command)}
                          className="rounded-md border border-[#d8dde3] bg-[#fafbfc] px-2.5 py-1 font-mono text-xs text-[#52616b] transition hover:border-[#9ac2b8] hover:bg-[#eef8f5] hover:text-[#1f6f61]"
                        >
                          {command}
                        </button>
                      ))}
                    </div>

                    <div className="mt-5 max-h-[560px] space-y-3 overflow-y-auto">
                      {operatorCommands.length === 0 ? (
                        <pre className="overflow-auto rounded-md border border-[#263244] bg-[#111827] p-4 text-xs leading-6 text-[#cbd5e1]">
                          No operator commands recorded for this session.
                        </pre>
                      ) : (
                        operatorCommands.map((record) => (
                          <article
                            key={record.id}
                            className="overflow-hidden rounded-md border border-[#263244] bg-[#111827]"
                          >
                            <div className="flex flex-col gap-2 border-b border-[#263244] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                              <code className="break-all text-sm font-semibold text-[#7dd3c7]">
                                pm3 &gt; {record.command}
                              </code>
                              <div className="flex items-center gap-2 text-xs">
                                <span
                                  className={
                                    record.success ? "text-[#86efac]" : "text-[#fca5a5]"
                                  }
                                >
                                  {record.success ? "Succeeded" : "Failed"}
                                </span>
                                <span className="text-[#94a3b8]">
                                  {formatDate(record.created_at)}
                                </span>
                              </div>
                            </div>
                            {record.error ? (
                              <p className="border-b border-[#263244] px-4 py-2 text-sm text-[#fca5a5]">
                                {record.error}
                              </p>
                            ) : null}
                            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words p-4 text-xs leading-6 text-[#e2e8f0]">
                              {record.output || "Command returned no output."}
                            </pre>
                          </article>
                        ))
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="p-5 text-sm text-[#52616b]">
                    Operator commands are available in Proxmark sessions.
                  </div>
                )}
              </section>

              {sessionAssurance ? (
                <section className={`rounded-lg border border-[#cbd6dc] bg-white shadow-sm ${["overview", "analysis"].includes(activeWorkspace) ? "" : "hidden"}`}>
                  <div className="flex flex-col gap-4 border-b border-[#edf0f2] p-5 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-[#17202a]">
                        Session Security Scores
                      </h2>
                      <p className="mt-1 text-sm text-[#52616b]">
                        Policy posture across every credential captured in this session.
                      </p>
                    </div>
                    <label className="block w-full sm:w-64">
                      <span className="text-xs font-semibold uppercase text-[#6b7780]">
                        Policy profile
                      </span>
                      <select
                        value={selectedAssurancePolicy}
                        onChange={(event) => setSelectedAssurancePolicy(event.target.value)}
                        disabled={isLoading}
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

                  <div className="grid gap-5 p-5 sm:grid-cols-2 xl:grid-cols-5">
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Average score
                      </p>
                      <p className="mt-1 text-3xl font-semibold text-[#17202a]">
                        {sessionAssurance.average_score ?? "-"}
                        {sessionAssurance.average_score !== null ? (
                          <span className="text-sm font-medium text-[#6b7780]">/10</span>
                        ) : null}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Lowest score
                      </p>
                      <p className="mt-1 text-3xl font-semibold text-[#17202a]">
                        {sessionAssurance.lowest_score ?? "-"}
                        {sessionAssurance.lowest_score !== null ? (
                          <span className="text-sm font-medium text-[#6b7780]">/10</span>
                        ) : null}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Credentials
                      </p>
                      <p className="mt-1 text-3xl font-semibold text-[#17202a]">
                        {sessionAssurance.card_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Critical failures
                      </p>
                      <p className={`mt-1 text-3xl font-semibold ${
                        sessionAssurance.critical_failure_count > 0
                          ? "text-[#9b2c2c]"
                          : "text-[#1f6f61]"
                      }`}>
                        {sessionAssurance.critical_failure_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-[#6b7780]">
                        Insufficient evidence
                      </p>
                      <p className={`mt-1 text-3xl font-semibold ${
                        sessionAssurance.insufficient_evidence_count > 0
                          ? "text-[#6d5a12]"
                          : "text-[#1f6f61]"
                      }`}>
                        {sessionAssurance.insufficient_evidence_count}
                      </p>
                    </div>
                  </div>

                  <p className="border-t border-[#edf0f2] px-5 py-4 text-sm leading-6 text-[#52616b]">
                    {sessionAssurance.summary}
                  </p>

                  {sessionAssurance.cards.length > 0 ? (
                    <div className="overflow-x-auto border-t border-[#edf0f2]">
                      <table className="w-full min-w-[900px] border-collapse text-left text-sm">
                        <thead className="bg-[#fafbfc] text-xs uppercase text-[#52616b]">
                          <tr>
                            <th className="px-5 py-3 font-semibold">Credential</th>
                            <th className="px-5 py-3 font-semibold">Credential rating</th>
                            <th className="px-5 py-3 font-semibold">Access path</th>
                            <th className="px-5 py-3 font-semibold">Posture</th>
                            <th className="px-5 py-3 font-semibold">Coverage</th>
                            <th className="px-5 py-3 font-semibold">Policy</th>
                            <th className="px-5 py-3 font-semibold">Critical</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#edf0f2]">
                          {sessionAssurance.cards.map((item) => (
                            <tr key={item.card_id}>
                              <td className="px-5 py-4">
                                <Link
                                  href={`/cards/${item.card_id}`}
                                  className="font-mono text-[#17202a] underline-offset-4 hover:text-[#2f6f73] hover:underline"
                                >
                                  {item.uid}
                                </Link>
                                <p className="mt-1 text-xs text-[#6b7780]">{item.card_type}</p>
                              </td>
                              <td className="px-5 py-4 text-lg font-semibold text-[#17202a]">
                                {item.credential_score ?? "-"}/10
                                <p className="mt-1 text-xs font-normal text-[#6b7780]">
                                  {item.credential_coverage_percent}% card evidence
                                </p>
                              </td>
                              <td className="px-5 py-4 text-lg font-semibold text-[#17202a]">
                                {item.score ?? "-"}/10
                                <p className="mt-1 text-xs font-normal text-[#6b7780]">
                                  Range {item.score_lower_bound}-{item.score_upper_bound}
                                </p>
                              </td>
                              <td className="px-5 py-4">
                                <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${
                                  assuranceStyles[item.grade] ?? assuranceStyles.inconclusive
                                }`}>
                                  {item.grade_label}
                                </span>
                              </td>
                              <td className="px-5 py-4 text-[#36454f]">
                                {item.coverage_percent}% / {item.confidence}
                              </td>
                              <td className="px-5 py-4">
                                <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                                  policyStatusStyles[item.policy_status] ?? policyStatusStyles.insufficient_evidence
                                }`}>
                                  {item.policy_status.replaceAll("_", " ")}
                                </span>
                              </td>
                              <td className="px-5 py-4 font-semibold">
                                <span className={item.critical_failure ? "text-[#9b2c2c]" : "text-[#1f6f61]"}>
                                  {item.critical_failure ? "Yes" : "No"}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className={`rounded-lg border border-[#d8dde3] bg-white shadow-sm ${["overview", "evidence"].includes(activeWorkspace) ? "" : "hidden"}`}>
                <div className="border-b border-[#edf0f2] p-5">
                  <h2 className="text-lg font-semibold text-[#17202a]">
                    Detected Cards
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] border-collapse text-left text-sm">
                    <thead className="bg-[#fafbfc] text-xs uppercase text-[#52616b]">
                      <tr>
                        <th className="px-5 py-3 font-semibold">UID</th>
                        <th className="px-5 py-3 font-semibold">Type</th>
                        <th className="px-5 py-3 font-semibold">Technology</th>
                        <th className="px-5 py-3 font-semibold">Frequency</th>
                        <th className="px-5 py-3 font-semibold">Protocol</th>
                        <th className="px-5 py-3 font-semibold">Risk</th>
                        <th className="px-5 py-3 font-semibold">Detected</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#edf0f2]">
                      {cards.length === 0 ? (
                        <tr>
                          <td
                            colSpan={7}
                            className="px-5 py-10 text-center font-medium text-[#6b7780]"
                          >
                            No cards detected yet
                          </td>
                        </tr>
                      ) : (
                        cards.map((card) => (
                          <tr key={card.id}>
                            <td className="break-all px-5 py-4 font-mono text-[#17202a]">
                              <button
                                type="button"
                                onClick={() => router.push(`/cards/${card.id}`)}
                                className="underline-offset-4 transition hover:text-[#2f6f73] hover:underline"
                              >
                                {card.uid}
                              </button>
                            </td>
                            <td className="px-5 py-4 font-semibold text-[#17202a]">
                              {card.card_type}
                            </td>
                            <td className="px-5 py-4 text-[#36454f]">
                              {card.technology}
                            </td>
                            <td className="px-5 py-4 text-[#36454f]">
                              {card.frequency}
                            </td>
                            <td className="px-5 py-4 text-[#36454f]">
                              {card.protocol}
                            </td>
                            <td className="px-5 py-4">
                              <span
                                className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                                  riskStyles[card.risk_level] ??
                                  "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                                }`}
                              >
                                {card.risk_level}
                              </span>
                            </td>
                            <td className="px-5 py-4 text-[#36454f]">
                              {formatDate(card.created_at)}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className={`rounded-lg border border-[#d8dde3] bg-white shadow-sm ${["analysis", "evidence"].includes(activeWorkspace) ? "" : "hidden"}`}>
                <div className="border-b border-[#edf0f2] p-5">
                  <h2 className="text-lg font-semibold text-[#17202a]">
                    Risk Findings
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1280px] border-collapse text-left text-sm">
                    <thead className="bg-[#fafbfc] text-xs uppercase text-[#52616b]">
                      <tr>
                        <th className="px-5 py-3 font-semibold">Finding</th>
                        <th className="px-5 py-3 font-semibold">Risk</th>
                        <th className="px-5 py-3 font-semibold">Analyst Review</th>
                        <th className="px-5 py-3 font-semibold">Card</th>
                        <th className="px-5 py-3 font-semibold">
                          Recommendation
                        </th>
                        <th className="px-5 py-3 font-semibold">Created</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#edf0f2]">
                      {findings.length === 0 ? (
                        <tr>
                          <td
                            colSpan={6}
                            className="px-5 py-10 text-center font-medium text-[#6b7780]"
                          >
                            No risk findings yet
                          </td>
                        </tr>
                      ) : (
                        findings.map((finding) => (
                          <tr key={finding.id}>
                            <td className="px-5 py-4">
                              <p className="font-semibold text-[#17202a]">
                                {finding.title}
                              </p>
                              <p className="mt-1 max-w-xl text-[#52616b]">
                                {finding.description}
                              </p>
                            </td>
                            <td className="px-5 py-4">
                              <span
                                className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                                  riskStyles[finding.risk_level] ??
                                  "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                                }`}
                              >
                                {finding.risk_level}
                              </span>
                            </td>
                            <td className="min-w-[320px] px-5 py-4 align-top">
                              <select
                                aria-label={`Review status for ${finding.title}`}
                                value={
                                  reviewDrafts[finding.id]?.review_status ??
                                  finding.review_status
                                }
                                onChange={(event) =>
                                  setReviewDrafts((current) => ({
                                    ...current,
                                    [finding.id]: {
                                      review_status: event.target
                                        .value as FindingReviewStatus,
                                      analyst_notes:
                                        current[finding.id]?.analyst_notes ??
                                        finding.analyst_notes ??
                                        "",
                                    },
                                  }))
                                }
                                className={`w-full rounded-md border px-3 py-2 text-sm font-semibold capitalize outline-none focus:ring-2 focus:ring-[#cfe7e5] ${
                                  reviewStyles[
                                    reviewDrafts[finding.id]?.review_status ??
                                      finding.review_status
                                  ]
                                }`}
                              >
                                <option value="open">Open</option>
                                <option value="confirmed">Confirmed</option>
                                <option value="accepted">Accepted</option>
                                <option value="false_positive">False positive</option>
                                <option value="resolved">Resolved</option>
                              </select>
                              <textarea
                                aria-label={`Analyst notes for ${finding.title}`}
                                rows={3}
                                value={
                                  reviewDrafts[finding.id]?.analyst_notes ??
                                  finding.analyst_notes ??
                                  ""
                                }
                                onChange={(event) =>
                                  setReviewDrafts((current) => ({
                                    ...current,
                                    [finding.id]: {
                                      review_status:
                                        current[finding.id]?.review_status ??
                                        finding.review_status,
                                      analyst_notes: event.target.value,
                                    },
                                  }))
                                }
                                placeholder="Analyst notes"
                                className="mt-2 w-full resize-y rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                              />
                              <div className="mt-2 flex items-center justify-between gap-3">
                                <span className="text-xs text-[#6b7780]">
                                  {finding.reviewed_at
                                    ? `Reviewed ${formatDate(finding.reviewed_at)}`
                                    : "Not reviewed"}
                                </span>
                                <button
                                  type="button"
                                  disabled={activeAction === `finding-${finding.id}`}
                                  onClick={() =>
                                    void handleFindingReview(finding.id)
                                  }
                                  className="shrink-0 rounded-md bg-[#2f6f73] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#255b5f] disabled:cursor-not-allowed disabled:bg-[#8daaad]"
                                >
                                  {activeAction === `finding-${finding.id}`
                                    ? "Saving..."
                                    : "Save Review"}
                                </button>
                              </div>
                            </td>
                            <td className="px-5 py-4">
                              <button
                                type="button"
                                onClick={() =>
                                  router.push(`/cards/${finding.card_id}`)
                                }
                                className="max-w-[220px] truncate text-left font-mono text-[#17202a] underline-offset-4 transition hover:text-[#2f6f73] hover:underline"
                              >
                                {cardLabelById.get(finding.card_id) ??
                                  `Card ${finding.card_id}`}
                              </button>
                            </td>
                            <td className="px-5 py-4 text-[#36454f]">
                              {finding.recommendation}
                            </td>
                            <td className="px-5 py-4 text-[#36454f]">
                              {formatDate(finding.created_at)}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className={`rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm ${activeWorkspace === "evidence" ? "" : "hidden"}`}>
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Latest Raw Evidence
                </h2>
                <pre className="mt-5 max-h-80 overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                  {latestCardEvidence
                    ? JSON.stringify(latestCardEvidence, null, 2)
                    : "No simulated evidence yet."}
                </pre>
              </section>
            </section>
          </div>
        ) : (
          <div className="mt-8 rounded-lg border border-[#d8dde3] bg-white p-10 text-center text-sm font-medium text-[#6b7780] shadow-sm">
            Session was not found.
          </div>
        )}
      </section>
    </main>
  );
}
