export type ScanSession = {
  id: number;
  session_name: string;
  description: string | null;
  mode: string;
  status: string;
  environment: string;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DetectedCard = {
  id: number;
  session_id: number;
  technology: string;
  frequency: string;
  card_type: string;
  protocol: string;
  uid: string;
  risk_level: string;
  normalized_data_json: Record<string, unknown>;
  raw_output_json: Record<string, unknown>;
  created_at: string;
};

export type Finding = {
  id: number;
  session_id: number;
  card_id: number;
  title: string;
  description: string;
  risk_level: string;
  recommendation: string;
  evidence_json: Record<string, unknown>;
  review_status: FindingReviewStatus;
  analyst_notes: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FindingReviewStatus =
  | "open"
  | "confirmed"
  | "accepted"
  | "false_positive"
  | "resolved";

export type FindingUpdatePayload = {
  review_status?: FindingReviewStatus;
  analyst_notes?: string | null;
};

export type OperatorCommand = {
  id: number;
  session_id: number;
  command: string;
  status: string;
  success: boolean;
  exit_code: number | null;
  output: string;
  error: string | null;
  created_at: string;
};

export type OperatorRecipe = {
  key: string;
  name: string;
  description: string;
  protocol: string;
  safety_tier: string;
  command_keys: string[];
  commands: string[];
  expected_evidence: string[];
};

export type CommandCapability = {
  key: string;
  command: string;
  name: string;
  protocol: string;
  category: string;
  safety_tier: string;
  operation: string;
  selector: string;
  read_only: boolean;
  changes_state: boolean;
  expected_evidence: string[];
};

export type CapabilityRegistry = {
  version: string;
  scope: string;
  commands: CommandCapability[];
  recipes: OperatorRecipe[];
};

export type EvidenceGap = {
  criterion_id: string;
  criterion_name: string;
  detail: string;
};

export type GuidedCard = {
  card_id: number;
  card_type: string;
  technology: string;
  score: number | null;
  score_lower_bound: number;
  score_upper_bound: number;
  coverage_percent: number;
  policy_status: string;
  critical_failure: boolean;
  evidence_gaps: EvidenceGap[];
};

export type EvidenceRecommendation = {
  id: string;
  rank: number;
  priority: "now" | "next" | "later";
  category: string;
  scope: string;
  card_ids: number[];
  title: string;
  rationale: string;
  expected_evidence: string[];
  safety_tier: string;
  action_type: "recipe" | "navigate" | "manual";
  recipe_key: string | null;
  href: string | null;
  target_workspace: string | null;
  can_execute: boolean;
  blocking_reason: string | null;
};

export type GuidedEvidence = {
  engine_version: string;
  registry_version: string;
  generated_at: string;
  session_id: number;
  policy_id: string;
  overall_status: string;
  card_count: number;
  average_coverage_percent: number;
  critical_path_count: number;
  open_gap_count: number;
  executable_recommendation_count: number;
  cards: GuidedCard[];
  recommendations: EvidenceRecommendation[];
};

export type OperatorRecipeRun = {
  recipe: OperatorRecipe;
  status: string;
  command_count: number;
  successful_count: number;
  results: OperatorCommand[];
};

export type DatasetMatchDetail = {
  field: string;
  points: number;
  observed: unknown;
  dataset: unknown;
};

export type CardDatasetMatch = {
  sample_index: number;
  score: number;
  confidence: string;
  source: string;
  dataset: string | null;
  source_path: string | null;
  source_file: string | null;
  source_sha256: string | null;
  card_type: string | null;
  protocol: string | null;
  uid: string | null;
  risk_level: string | null;
  match_reasons: string[];
  match_details: DatasetMatchDetail[];
};

export type CardDatasetCorrelation = {
  scorer_version: string;
  evaluated_samples: number;
  observed_features: Record<string, unknown>;
  best_score: number;
  confidence: string;
  match_count: number;
  matches: CardDatasetMatch[];
};

export type CredentialDifference = {
  field: string;
  target: unknown;
  observed: unknown;
};

export type CredentialObservation = {
  card_id: number;
  session_id: number;
  created_at: string;
  source: string | null;
  card_type: string;
  protocol: string;
  fingerprint: string;
  matching_fields: string[];
  differences: CredentialDifference[];
};

export type CardIntelligence = {
  fingerprint_version: string;
  card_id: number;
  uid: string;
  fingerprint: string;
  observation_count: number;
  session_count: number;
  cross_session_duplicate: boolean;
  inconsistent_identity: boolean;
  non_unique_uid: boolean;
  risk_level: string;
  confidence: string;
  summary: string;
  compared_fields: string[];
  target_features: Record<string, unknown>;
  observations: CredentialObservation[];
};

export type AssuranceOutcome = "pass" | "partial" | "fail" | "unknown";

export type AssuranceCriterionDefinition = {
  id: string;
  name: string;
  description: string;
  max_points: number;
  levels: Record<string, string>;
};

export type AssurancePolicy = {
  id: string;
  name: string;
  version: string;
  description: string;
  use_case: string;
  strictness: string;
  minimum_score: number;
  minimum_coverage_percent: number;
  reject_critical_failures: boolean;
  criteria: AssuranceCriterionDefinition[];
};

export type AssuranceCriterionResult = {
  id: string;
  name: string;
  outcome: AssuranceOutcome;
  rating: number | null;
  max_points: number;
  critical: boolean;
  summary: string;
  evidence: string[];
  recommendations: string[];
};

export type AnalystReviewSummary = {
  status: "not_started" | "in_progress" | "complete";
  finding_count: number;
  active_finding_count: number;
  reviewed_finding_count: number;
  unresolved_high_count: number;
};

export type CardAssurance = {
  engine_version: string;
  methodology_version: string;
  evaluated_at: string;
  policy: AssurancePolicy;
  card_id: number;
  credential_score: number | null;
  credential_coverage_percent: number;
  credential_grade: string;
  credential_grade_label: string;
  score: number | null;
  scale_max: number;
  score_lower_bound: number;
  score_upper_bound: number;
  unknown_criteria_count: number;
  grade: string;
  grade_label: string;
  coverage_percent: number;
  confidence: string;
  policy_status: "pass" | "fail" | "insufficient_evidence";
  meets_policy: boolean | null;
  critical_failure: boolean;
  summary: string;
  criteria: AssuranceCriterionResult[];
  recommendations: string[];
  analyst_review: AnalystReviewSummary;
  evidence_snapshot: Record<string, unknown>;
};

export type SessionCardAssurance = {
  card_id: number;
  uid: string;
  card_type: string;
  credential_score: number | null;
  credential_coverage_percent: number;
  credential_grade: string;
  credential_grade_label: string;
  score: number | null;
  score_lower_bound: number;
  score_upper_bound: number;
  grade: string;
  grade_label: string;
  coverage_percent: number;
  confidence: string;
  policy_status: "pass" | "fail" | "insufficient_evidence";
  critical_failure: boolean;
};

export type CardAssuranceEvidence = {
  id: number;
  card_id: number;
  reader_enforcement: "uid_only" | "partial" | "cryptographic" | null;
  lifecycle_monitoring: "absent" | "partial" | "managed" | null;
  evidence_source: string;
  confidence: "low" | "medium" | "high";
  notes: string | null;
  assessed_at: string;
  created_at: string;
  updated_at: string;
};

export type CardAssuranceEvidencePayload = {
  reader_enforcement: CardAssuranceEvidence["reader_enforcement"];
  lifecycle_monitoring: CardAssuranceEvidence["lifecycle_monitoring"];
  evidence_source: string;
  confidence: CardAssuranceEvidence["confidence"];
  notes?: string | null;
  assessed_at: string;
};

export type SessionAssurance = {
  engine_version: string;
  methodology_version: string;
  evaluated_at: string;
  policy: AssurancePolicy;
  session_id: number;
  card_count: number;
  average_score: number | null;
  lowest_score: number | null;
  critical_failure_count: number;
  insufficient_evidence_count: number;
  grade_counts: Record<string, number>;
  policy_status_counts: Record<string, number>;
  summary: string;
  cards: SessionCardAssurance[];
};

export type TraceProtocol = "14a" | "mf" | "des" | "7816" | "15" | "iclass";

export type TraceFrame = {
  sequence: number;
  start: number;
  end: number;
  duration: number;
  source: string;
  direction: string;
  data_hex: string;
  byte_count: number;
  crc: string | null;
  annotation: string | null;
  parity_error: boolean;
  short_frame: boolean;
  command: string | null;
  apdu: Record<string, unknown> | null;
};

export type TraceFinding = {
  rule_id: string;
  title: string;
  risk_level: string;
  confidence: string;
  description: string;
  recommendation: string;
  evidence: string[];
  frame_sequences: number[];
};

export type TransactionTraceSummary = {
  id: number;
  session_id: number;
  name: string;
  protocol: string;
  source: string;
  status: string;
  risk_level: string;
  confidence: string;
  frame_count: number;
  reader_frame_count: number;
  card_frame_count: number;
  apdu_count: number;
  raw_sha256: string;
  summary_json: Record<string, unknown>;
  created_at: string;
};

export type TransactionTrace = TransactionTraceSummary & {
  frames_json: TraceFrame[];
  findings_json: TraceFinding[];
  raw_output: string;
};

export type TraceAnalyzePayload = {
  name: string;
  protocol: TraceProtocol;
  raw_output: string;
};

export type TraceBufferPayload = {
  name: string;
  protocol: TraceProtocol;
};

export type AssessmentEvent = {
  id: number;
  assessment_run_id: number;
  session_id: number;
  sequence: number;
  phase: string;
  status: string;
  title: string;
  command: string | null;
  message: string;
  evidence_json: Record<string, unknown>;
  created_at: string;
};

export type AssessmentRun = {
  id: number;
  session_id: number;
  profile: string;
  status: string;
  detected_card_count: number;
  summary_json: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  events: AssessmentEvent[];
};

export type SessionCreatePayload = {
  session_name: string;
  description?: string | null;
  mode?: string;
  environment?: string;
};

export type ExperimentBatch = {
  id: number;
  session_id: number;
  name: string;
  condition: "baseline" | "post_remediation";
  status: "open" | "completed";
  authorization_reference: string;
  operator_label: string;
  location_label: string;
  device_model: string;
  client_version: string;
  firmware_version: string;
  antenna_configuration: string;
  host_os: string;
  command_profile: string;
  environment_notes: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ExperimentBatchCreatePayload = {
  name: string;
  condition: "baseline" | "post_remediation";
  authorization_reference: string;
  operator_label: string;
  location_label: string;
  device_model: string;
  client_version: string;
  firmware_version: string;
  antenna_configuration: string;
  host_os: string;
  command_profile: string;
  environment_notes?: string | null;
};

export type MeasurementTrial = {
  id: number;
  session_id: number;
  batch_id: number;
  source_card_id: number | null;
  trial_number: number;
  credential_alias: string;
  technology_family: string;
  card_family: string | null;
  distance_cm: number;
  orientation: "parallel" | "perpendicular" | "edge" | "custom";
  presented_face: "front" | "back" | "not_applicable";
  success: boolean;
  classification_result: "correct" | "incorrect" | "inconclusive";
  identification_duration_ms: number;
  metadata_fields_count: number;
  data_extracted_bytes: number | null;
  nearby_metal: boolean;
  rf_interference: "none" | "low" | "moderate" | "high" | "unknown";
  environment_notes: string | null;
  notes: string | null;
  raw_evidence_sha256: string | null;
  created_at: string;
  updated_at: string;
};

export type MeasurementTrialCreatePayload = {
  batch_id: number;
  source_card_id?: number | null;
  credential_alias: string;
  technology_family?: string | null;
  card_family?: string | null;
  distance_cm: number;
  orientation: MeasurementTrial["orientation"];
  presented_face: MeasurementTrial["presented_face"];
  success: boolean;
  classification_result: MeasurementTrial["classification_result"];
  identification_duration_ms: number;
  metadata_fields_count: number;
  data_extracted_bytes?: number | null;
  nearby_metal: boolean;
  rf_interference: MeasurementTrial["rf_interference"];
  environment_notes?: string | null;
  notes?: string | null;
};

export type LiveMeasurementTrialPayload = {
  batch_id: number;
  source_card_id: number;
  credential_alias: string;
  band: "hf" | "lf";
  distance_cm: number;
  orientation: MeasurementTrial["orientation"];
  presented_face: MeasurementTrial["presented_face"];
  nearby_metal: boolean;
  rf_interference: MeasurementTrial["rf_interference"];
  environment_notes?: string | null;
  notes?: string | null;
};

export type LiveMeasurementTrialResult = {
  trial: MeasurementTrial;
  command: string;
  detected: boolean;
  observed_card_type: string | null;
  observed_uid: string | null;
  uid_match: boolean | null;
  evidence_path: string | null;
  message: string;
};

export type TimingStatistics = {
  count: number;
  minimum_ms: number | null;
  maximum_ms: number | null;
  median_ms: number | null;
  q1_ms: number | null;
  q3_ms: number | null;
};

export type ReliableDistanceResult = {
  credential_alias: string;
  technology_family: string;
  orientation: string;
  presented_face: string;
  reliable_distance_cm: number;
  attempts: number;
  successes: number;
};

export type TechnologyMeasurementSummary = {
  technology_family: string;
  trial_count: number;
  unique_credentials: number;
  successful_trials: number;
  detection_success_rate: number;
  classified_trials: number;
  correct_classifications: number;
  classification_accuracy: number | null;
  timing: TimingStatistics;
  average_metadata_fields: number;
  total_extracted_bytes: number;
};

export type MeasurementSummary = {
  methodology_version: string;
  session_id: number;
  batch_count: number;
  trial_count: number;
  unique_credentials: number;
  successful_trials: number;
  detection_success_rate: number;
  classified_trials: number;
  correct_classifications: number;
  classification_accuracy: number | null;
  timing: TimingStatistics;
  reliable_distances: ReliableDistanceResult[];
  technologies: TechnologyMeasurementSummary[];
};

export type ProportionStatistics = {
  events: number;
  attempts: number;
  rate_percent: number;
  ci_lower_percent: number;
  ci_upper_percent: number;
};

export type MeasurementConditionAnalysis = {
  credential_alias: string;
  source_card_id: number | null;
  technology_family: string;
  card_family: string | null;
  distance_cm: number;
  orientation: string;
  presented_face: string;
  detection: ProportionStatistics;
  correct_identification: ProportionStatistics;
  partial_response_count: number;
  incorrect_classification_count: number;
  inconclusive_count: number;
  correct_identification_timing: TimingStatistics;
  meets_minimum_repetitions: boolean;
};

export type CredentialMeasurementAnalysis = {
  credential_alias: string;
  source_card_id: number | null;
  technology_family: string;
  card_family: string | null;
  trial_count: number;
  condition_count: number;
  maximum_tested_distance_cm: number;
  reliable_identification_distance_cm: number | null;
  detection: ProportionStatistics;
  correct_identification: ProportionStatistics;
  partial_response_count: number;
  correct_identification_timing: TimingStatistics;
};

export type MeasurementQualityFlag = {
  id: string;
  severity: "info" | "warning" | "high";
  category: string;
  scope: string;
  title: string;
  detail: string;
};

export type MeasurementAnalysis = {
  analysis_version: string;
  methodology_version: string;
  session_id: number;
  batch_id: number | null;
  confidence_level_percent: number;
  interval_method: string;
  minimum_attempts_per_condition: number;
  trial_count: number;
  credential_count: number;
  condition_count: number;
  credentials: CredentialMeasurementAnalysis[];
  conditions: MeasurementConditionAnalysis[];
  quality_flags: MeasurementQualityFlag[];
  interpretation: string[];
};

export type ReliableDistanceChange = {
  credential_alias: string;
  technology_family: string;
  orientation: string;
  presented_face: string;
  baseline_distance_cm: number | null;
  post_remediation_distance_cm: number | null;
  delta_cm: number | null;
};

export type MeasurementComparison = {
  methodology_version: string;
  session_id: number;
  baseline_batch: ExperimentBatch;
  post_remediation_batch: ExperimentBatch;
  baseline_summary: MeasurementSummary;
  post_remediation_summary: MeasurementSummary;
  detection_rate_delta: number;
  classification_accuracy_delta: number | null;
  median_duration_delta_ms: number | null;
  trial_count_delta: number;
  unique_credentials_delta: number;
  reliable_distance_changes: ReliableDistanceChange[];
  interpretation: string[];
};

export type SimulatedScanPayload = {
  technology?: string | null;
  card_type?: string | null;
  source?: string | null;
  dataset?: string | null;
  file_type?: string | null;
  uid?: string | null;
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the generic request message when the backend does not return JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function listSessions(): Promise<ScanSession[]> {
  return apiRequest<ScanSession[]>("/api/v1/sessions");
}

export function getSession(sessionId: number): Promise<ScanSession> {
  return apiRequest<ScanSession>(`/api/v1/sessions/${sessionId}`);
}

export function createSession(
  payload: SessionCreatePayload,
): Promise<ScanSession> {
  return apiRequest<ScanSession>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startSession(sessionId: number): Promise<ScanSession> {
  return apiRequest<ScanSession>(`/api/v1/sessions/${sessionId}/start`, {
    method: "POST",
  });
}

export function stopSession(sessionId: number): Promise<ScanSession> {
  return apiRequest<ScanSession>(`/api/v1/sessions/${sessionId}/stop`, {
    method: "POST",
  });
}

export function simulateSessionScan(
  sessionId: number,
  payload: SimulatedScanPayload = {},
): Promise<DetectedCard> {
  return apiRequest<DetectedCard>(
    `/api/v1/sessions/${sessionId}/scan/simulate`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listSessionCards(sessionId: number): Promise<DetectedCard[]> {
  return apiRequest<DetectedCard[]>(`/api/v1/sessions/${sessionId}/cards`);
}

export function listExperimentBatches(
  sessionId: number,
): Promise<ExperimentBatch[]> {
  return apiRequest<ExperimentBatch[]>(
    `/api/v1/sessions/${sessionId}/experiment-batches`,
  );
}

export function createExperimentBatch(
  sessionId: number,
  payload: ExperimentBatchCreatePayload,
): Promise<ExperimentBatch> {
  return apiRequest<ExperimentBatch>(
    `/api/v1/sessions/${sessionId}/experiment-batches`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function updateExperimentBatch(
  sessionId: number,
  batchId: number,
  payload: Partial<ExperimentBatchCreatePayload> & {
    status?: "open" | "completed";
  },
): Promise<ExperimentBatch> {
  return apiRequest<ExperimentBatch>(
    `/api/v1/sessions/${sessionId}/experiment-batches/${batchId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function listMeasurementTrials(
  sessionId: number,
): Promise<MeasurementTrial[]> {
  return apiRequest<MeasurementTrial[]>(
    `/api/v1/sessions/${sessionId}/measurement-trials`,
  );
}

export function createMeasurementTrial(
  sessionId: number,
  payload: MeasurementTrialCreatePayload,
): Promise<MeasurementTrial> {
  return apiRequest<MeasurementTrial>(
    `/api/v1/sessions/${sessionId}/measurement-trials`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function runLiveMeasurementTrial(
  sessionId: number,
  payload: LiveMeasurementTrialPayload,
): Promise<LiveMeasurementTrialResult> {
  return apiRequest<LiveMeasurementTrialResult>(
    `/api/v1/sessions/${sessionId}/measurement-trials/live`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function deleteMeasurementTrial(
  sessionId: number,
  trialId: number,
): Promise<void> {
  return apiRequest<void>(
    `/api/v1/sessions/${sessionId}/measurement-trials/${trialId}`,
    { method: "DELETE" },
  );
}

export function getMeasurementSummary(
  sessionId: number,
): Promise<MeasurementSummary> {
  return apiRequest<MeasurementSummary>(
    `/api/v1/sessions/${sessionId}/measurement-summary`,
  );
}

export function getMeasurementAnalysis(
  sessionId: number,
  batchId?: number,
): Promise<MeasurementAnalysis> {
  const suffix = batchId ? `?batch_id=${batchId}` : "";
  return apiRequest<MeasurementAnalysis>(
    `/api/v1/sessions/${sessionId}/measurement-analysis${suffix}`,
  );
}

export function compareMeasurementBatches(
  sessionId: number,
  baselineBatchId: number,
  postRemediationBatchId: number,
): Promise<MeasurementComparison> {
  const query = new URLSearchParams({
    baseline_batch_id: String(baselineBatchId),
    post_remediation_batch_id: String(postRemediationBatchId),
  });
  return apiRequest<MeasurementComparison>(
    `/api/v1/sessions/${sessionId}/measurement-comparison?${query}`,
  );
}

export function exportMeasurementCsv(sessionId: number): Promise<string> {
  return downloadApiFile(
    `/api/v1/sessions/${sessionId}/reports/measurements.csv`,
    `pass-pac-session-${sessionId}-measurements.csv`,
  );
}

export function exportMeasurementAnalysisCsv(sessionId: number): Promise<string> {
  return downloadApiFile(
    `/api/v1/sessions/${sessionId}/reports/measurement-analysis.csv`,
    `pass-pac-session-${sessionId}-measurement-analysis.csv`,
  );
}

export function exportMeasurementPdf(
  sessionId: number,
  baselineBatchId?: number,
  postRemediationBatchId?: number,
): Promise<string> {
  const query = new URLSearchParams();
  if (baselineBatchId && postRemediationBatchId) {
    query.set("baseline_batch_id", String(baselineBatchId));
    query.set("post_remediation_batch_id", String(postRemediationBatchId));
  }
  const suffix = query.size ? `?${query}` : "";
  return downloadApiFile(
    `/api/v1/sessions/${sessionId}/reports/research-report.pdf${suffix}`,
    `pass-pac-session-${sessionId}-research-report.pdf`,
  );
}

async function downloadApiFile(
  path: string,
  fallbackFilename: string,
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST" });
  if (!response.ok) {
    let message = `Export failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the status message for non-JSON failures.
    }
    throw new Error(message);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encodedMatch = disposition.match(/filename\*=utf-8''([^;]+)/i);
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = encodedMatch
    ? decodeURIComponent(encodedMatch[1])
    : plainMatch?.[1] ?? fallbackFilename;
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}

export function listSessionFindings(sessionId: number): Promise<Finding[]> {
  return apiRequest<Finding[]>(`/api/v1/sessions/${sessionId}/findings`);
}

export function listSessionAssessments(
  sessionId: number,
): Promise<AssessmentRun[]> {
  return apiRequest<AssessmentRun[]>(
    `/api/v1/sessions/${sessionId}/assessments`,
  );
}

export function listSessionOperatorCommands(
  sessionId: number,
): Promise<OperatorCommand[]> {
  return apiRequest<OperatorCommand[]>(
    `/api/v1/sessions/${sessionId}/commands`,
  );
}

export function runSessionOperatorCommand(
  sessionId: number,
  command: string,
): Promise<OperatorCommand> {
  return apiRequest<OperatorCommand>(
    `/api/v1/sessions/${sessionId}/commands`,
    {
      method: "POST",
      body: JSON.stringify({ command }),
    },
  );
}

export function listSessionOperatorRecipes(
  sessionId: number,
): Promise<OperatorRecipe[]> {
  return apiRequest<OperatorRecipe[]>(
    `/api/v1/sessions/${sessionId}/recipes`,
  );
}

export function getSessionCapabilities(
  sessionId: number,
): Promise<CapabilityRegistry> {
  return apiRequest<CapabilityRegistry>(
    `/api/v1/sessions/${sessionId}/capabilities`,
  );
}

export function getSessionEvidenceGuidance(
  sessionId: number,
  policyId = "university-standard",
): Promise<GuidedEvidence> {
  return apiRequest<GuidedEvidence>(
    `/api/v1/sessions/${sessionId}/evidence-guidance?policy_id=${encodeURIComponent(policyId)}`,
  );
}

export function runSessionOperatorRecipe(
  sessionId: number,
  recipeKey: string,
): Promise<OperatorRecipeRun> {
  return apiRequest<OperatorRecipeRun>(
    `/api/v1/sessions/${sessionId}/recipes/${recipeKey}`,
    { method: "POST" },
  );
}

export function startAutomatedAssessment(
  sessionId: number,
  band: "hf" | "lf" | "emv" = "hf",
): Promise<AssessmentRun> {
  return apiRequest<AssessmentRun>(
    `/api/v1/sessions/${sessionId}/assessments`,
    {
      method: "POST",
      body: JSON.stringify({ band }),
    },
  );
}

export function listCards(): Promise<DetectedCard[]> {
  return apiRequest<DetectedCard[]>("/api/v1/cards");
}

export function getCard(cardId: number): Promise<DetectedCard> {
  return apiRequest<DetectedCard>(`/api/v1/cards/${cardId}`);
}

export function getCardDatasetCorrelation(
  cardId: number,
): Promise<CardDatasetCorrelation> {
  return apiRequest<CardDatasetCorrelation>(
    `/api/v1/cards/${cardId}/dataset-correlation`,
  );
}

export function getCardIntelligence(
  cardId: number,
): Promise<CardIntelligence> {
  return apiRequest<CardIntelligence>(`/api/v1/cards/${cardId}/intelligence`);
}

export function listAssurancePolicies(): Promise<AssurancePolicy[]> {
  return apiRequest<AssurancePolicy[]>("/api/v1/assurance/policies");
}

export function getCardAssurance(
  cardId: number,
  policyId = "university-standard",
): Promise<CardAssurance> {
  return apiRequest<CardAssurance>(
    `/api/v1/cards/${cardId}/assurance?policy_id=${encodeURIComponent(policyId)}`,
  );
}

export function getCardAssuranceEvidence(
  cardId: number,
): Promise<CardAssuranceEvidence | null> {
  return apiRequest<CardAssuranceEvidence | null>(
    `/api/v1/cards/${cardId}/assurance-evidence`,
  );
}

export function saveCardAssuranceEvidence(
  cardId: number,
  payload: CardAssuranceEvidencePayload,
): Promise<CardAssuranceEvidence> {
  return apiRequest<CardAssuranceEvidence>(
    `/api/v1/cards/${cardId}/assurance-evidence`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function deleteCardAssuranceEvidence(cardId: number): Promise<void> {
  return apiRequest<void>(`/api/v1/cards/${cardId}/assurance-evidence`, {
    method: "DELETE",
  });
}

export function getSessionAssurance(
  sessionId: number,
  policyId = "university-standard",
): Promise<SessionAssurance> {
  return apiRequest<SessionAssurance>(
    `/api/v1/sessions/${sessionId}/assurance?policy_id=${encodeURIComponent(policyId)}`,
  );
}

export function listSessionTransactionTraces(
  sessionId: number,
): Promise<TransactionTraceSummary[]> {
  return apiRequest<TransactionTraceSummary[]>(
    `/api/v1/sessions/${sessionId}/traces`,
  );
}

export function getSessionTransactionTrace(
  sessionId: number,
  traceId: number,
): Promise<TransactionTrace> {
  return apiRequest<TransactionTrace>(
    `/api/v1/sessions/${sessionId}/traces/${traceId}`,
  );
}

export function analyzeSessionTransactionTrace(
  sessionId: number,
  payload: TraceAnalyzePayload,
): Promise<TransactionTrace> {
  return apiRequest<TransactionTrace>(`/api/v1/sessions/${sessionId}/traces`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function analyzeSessionDeviceTraceBuffer(
  sessionId: number,
  payload: TraceBufferPayload,
): Promise<TransactionTrace> {
  return apiRequest<TransactionTrace>(
    `/api/v1/sessions/${sessionId}/traces/device-buffer`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function deleteSessionTransactionTrace(
  sessionId: number,
  traceId: number,
): Promise<void> {
  return apiRequest<void>(`/api/v1/sessions/${sessionId}/traces/${traceId}`, {
    method: "DELETE",
  });
}

export function listCardFindings(cardId: number): Promise<Finding[]> {
  return apiRequest<Finding[]>(`/api/v1/cards/${cardId}/findings`);
}

export function listFindings(): Promise<Finding[]> {
  return apiRequest<Finding[]>("/api/v1/findings");
}

export function getFinding(findingId: number): Promise<Finding> {
  return apiRequest<Finding>(`/api/v1/findings/${findingId}`);
}

export function updateFinding(
  findingId: number,
  payload: FindingUpdatePayload,
): Promise<Finding> {
  return apiRequest<Finding>(`/api/v1/findings/${findingId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteSession(sessionId: number): Promise<void> {
  return apiRequest<void>(`/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
  });
}
