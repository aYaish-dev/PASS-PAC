"use client";

import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CreditCard,
  Database,
  Fingerprint,
  RadioTower,
  RefreshCw,
  ScanLine,
  ShieldAlert,
  SquareTerminal,
  Usb,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, InlineAlert, LoadingState, PageHeader, SectionHeader, StatusBadge } from "../components/ui";
import { listCards, listFindings, listSessions } from "../lib/api";
import type { DetectedCard, Finding, ScanSession } from "../lib/api";

type ProxmarkStatus = {
  enabled: boolean;
  configured: boolean;
  connection_mode: string;
  bridge_url: string | null;
  bridge_available: boolean;
  client_path: string | null;
  client_available: boolean;
  port: string | null;
  detected_ports: string[];
  safe_commands: string[];
  integration_state: string;
  notes: string[];
};

type ProxmarkProbe = {
  command: string;
  success: boolean;
  exit_code: number | null;
  output: string;
  error: string | null;
};

type ProxmarkIdentify = {
  technology: string;
  command: string;
  success: boolean;
  exit_code: number | null;
  detected: boolean;
  card_type: string | null;
  protocol: string | null;
  uid: string | null;
  atqa: string | null;
  sak: string | null;
  fields: Record<string, string>;
  output: string;
  error: string | null;
  saved_observation_path: string | null;
};

type DatasetMatch = {
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
};

type CardProfile = {
  profile_id: string;
  first_seen: string;
  last_seen: string;
  observation_count: number;
  technology: string;
  card_type: string | null;
  protocol: string | null;
  uid: string | null;
  atqa: string | null;
  sak: string | null;
  fields: Record<string, string>;
  attention_level: string;
  findings: Array<{ level: string; title: string; detail: string }>;
  dataset_matches: DatasetMatch[];
  raw_output_preview: string;
};

type CardProfileReview = {
  summary: {
    total_observations: number;
    total_profiles: number;
    hf_profiles: number;
    lf_profiles: number;
    dataset_samples: number;
    dataset_matched_profiles: number;
    medium_attention_profiles: number;
    high_attention_profiles: number;
  };
  profiles: CardProfile[];
};

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

function formatTimestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value || "Unknown" : date.toLocaleString();
}

export default function Home() {
  const [sessions, setSessions] = useState<ScanSession[]>([]);
  const [cards, setCards] = useState<DetectedCard[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [proxmarkStatus, setProxmarkStatus] = useState<ProxmarkStatus | null>(null);
  const [probeResult, setProbeResult] = useState<ProxmarkProbe | null>(null);
  const [identifyResult, setIdentifyResult] = useState<ProxmarkIdentify | null>(null);
  const [profileReview, setProfileReview] = useState<CardProfileReview | null>(null);
  const [isLoadingDevice, setIsLoadingDevice] = useState(true);
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(true);
  const [isProbing, setIsProbing] = useState(false);
  const [identifyingTechnology, setIdentifyingTechnology] = useState<"hf" | "lf" | null>(null);
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const highRiskCount = findings.filter((finding) => finding.risk_level === "high").length;
  const runningSessions = sessions.filter((session) => session.status === "running").length;
  const deviceReady = Boolean(
    proxmarkStatus?.enabled && (proxmarkStatus.bridge_available || proxmarkStatus.client_available),
  );

  async function loadWorkspace() {
    setWorkspaceError(null);
    try {
      const [sessionData, cardData, findingData] = await Promise.all([
        listSessions(),
        listCards(),
        listFindings(),
      ]);
      setSessions(sessionData);
      setCards(cardData);
      setFindings(findingData);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "Unable to load workspace data.");
    }
  }

  async function loadProxmarkStatus() {
    setIsLoadingDevice(true);
    setDeviceError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/device/proxmark/status`);
      if (!response.ok) throw new Error(`Device status failed with ${response.status}`);
      setProxmarkStatus((await response.json()) as ProxmarkStatus);
    } catch (error) {
      setDeviceError(error instanceof Error ? error.message : "Unable to load device status.");
    } finally {
      setIsLoadingDevice(false);
    }
  }

  async function runProbe() {
    setIsProbing(true);
    setDeviceError(null);
    setProbeResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/device/proxmark/probe`, { method: "POST" });
      if (!response.ok) throw new Error(`Device probe failed with ${response.status}`);
      setProbeResult((await response.json()) as ProxmarkProbe);
      await loadProxmarkStatus();
    } catch (error) {
      setDeviceError(error instanceof Error ? error.message : "Unable to probe device.");
    } finally {
      setIsProbing(false);
    }
  }

  async function loadCardProfiles() {
    setIsLoadingProfiles(true);
    setProfileError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/cards/profiles`);
      if (!response.ok) throw new Error(`Card profiles failed with ${response.status}`);
      setProfileReview((await response.json()) as CardProfileReview);
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to load card profiles.");
    } finally {
      setIsLoadingProfiles(false);
    }
  }

  async function identifyCard(technology: "hf" | "lf") {
    setIdentifyingTechnology(technology);
    setDeviceError(null);
    setProbeResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/device/proxmark/identify/${technology}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(`Card identify failed with ${response.status}`);
      setIdentifyResult((await response.json()) as ProxmarkIdentify);
      await Promise.all([loadProxmarkStatus(), loadCardProfiles()]);
    } catch (error) {
      setDeviceError(error instanceof Error ? error.message : "Unable to identify card.");
    } finally {
      setIdentifyingTechnology(null);
    }
  }

  useEffect(() => {
    void loadWorkspace();
    void loadProxmarkStatus();
    void loadCardProfiles();
  }, []);

  const latestOutput = identifyResult?.output || probeResult?.output;

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Local assessment workspace"
        title="Operations overview"
        description="Monitor credential research, device readiness, and active evidence collection from one local console."
        actions={
          <>
            <button type="button" className="icon-button" onClick={() => void loadWorkspace()} title="Refresh workspace" aria-label="Refresh workspace">
              <RefreshCw size={17} />
            </button>
            <Link href="/sessions" className="btn btn-primary">
              <ScanLine size={16} /> New session
            </Link>
          </>
        }
      />

      {workspaceError ? <div className="mb-5"><InlineAlert>{workspaceError}</InlineAlert></div> : null}

      <section className="metric-grid" aria-label="Workspace metrics">
        <div className="metric-item">
          <span className="metric-label"><CalendarClock size={15} /> Sessions</span>
          <strong className="metric-value">{sessions.length}</strong>
          <span className="metric-note">{runningSessions} currently running</span>
        </div>
        <div className="metric-item">
          <span className="metric-label"><CreditCard size={15} /> Credentials</span>
          <strong className="metric-value">{cards.length}</strong>
          <span className="metric-note">Normalized observations</span>
        </div>
        <div className="metric-item">
          <span className="metric-label"><ShieldAlert size={15} /> High risk</span>
          <strong className="metric-value">{highRiskCount}</strong>
          <span className="metric-note">Findings requiring review</span>
        </div>
        <div className="metric-item">
          <span className="metric-label"><Database size={15} /> Dataset matches</span>
          <strong className="metric-value">{profileReview?.summary.dataset_matched_profiles ?? 0}</strong>
          <span className="metric-note">Flipper-derived correlations</span>
        </div>
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <section className="panel">
          <div className="panel-heading">
            <SectionHeader
              title="Recent sessions"
              description="Authorized assessment workspaces and their latest state."
              action={<Link href="/sessions" className="btn btn-secondary">View all <ArrowRight size={15} /></Link>}
            />
          </div>
          {sessions.length === 0 ? (
            <EmptyState title="No sessions recorded" description="Create a session to establish an evidence boundary before acquisition." />
          ) : (
            <div className="data-table-wrap">
              <table className="data-table data-table-compact">
                <thead><tr><th>Session</th><th>Mode</th><th>Status</th><th>Cards</th><th aria-label="Open session" /></tr></thead>
                <tbody>
                  {sessions.slice(0, 6).map((session) => (
                    <tr key={session.id}>
                      <td>
                        <Link href={`/sessions/${session.id}`} className="font-semibold text-slate-900 hover:text-teal-700">
                          {session.session_name}
                        </Link>
                        <div className="mt-1 max-w-md truncate text-xs text-slate-500">{session.description || "No description"}</div>
                      </td>
                      <td className="capitalize">{session.mode}</td>
                      <td><StatusBadge status={session.status} /></td>
                      <td className="mono">{cards.filter((card) => card.session_id === session.id).length}</td>
                      <td className="text-right"><Link href={`/sessions/${session.id}`} className="icon-button" title={`Open ${session.session_name}`} aria-label={`Open ${session.session_name}`}><ArrowRight size={16} /></Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="panel">
          <div className="panel-heading">
            <SectionHeader
              title="Proxmark3 station"
              description="Easy 512K acquisition device on this workstation."
              action={<StatusBadge status={deviceReady ? "ready" : proxmarkStatus?.integration_state ?? "checking"} />}
            />
          </div>
          <div className="panel-body">
            {deviceError ? <InlineAlert>{deviceError}</InlineAlert> : null}
            {isLoadingDevice ? (
              <LoadingState label="Checking device connection" />
            ) : proxmarkStatus ? (
              <>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                  <div><dt className="text-xs font-semibold text-slate-500">Connection</dt><dd className="mt-1 font-semibold capitalize text-slate-900">{proxmarkStatus.connection_mode}</dd></div>
                  <div><dt className="text-xs font-semibold text-slate-500">Port</dt><dd className="mono mt-1 text-slate-900">{proxmarkStatus.port ?? "Not set"}</dd></div>
                  <div><dt className="text-xs font-semibold text-slate-500">Bridge</dt><dd className="mt-1 text-slate-900">{proxmarkStatus.bridge_available ? "Reachable" : "Unavailable"}</dd></div>
                  <div><dt className="text-xs font-semibold text-slate-500">Client</dt><dd className="mt-1 text-slate-900">{proxmarkStatus.client_available ? "Available" : "Unavailable"}</dd></div>
                </dl>

                <div className="mt-5 border-t border-slate-200 pt-5">
                  <p className="mb-3 text-xs font-bold text-slate-600">Direct identification</p>
                  <div className="grid grid-cols-2 gap-2">
                    <button type="button" className="btn btn-teal" disabled={!proxmarkStatus.enabled || isProbing || identifyingTechnology !== null} onClick={() => void identifyCard("hf")}>
                      <RadioTower size={16} /> {identifyingTechnology === "hf" ? "Reading" : "HF / NFC"}
                    </button>
                    <button type="button" className="btn btn-primary" disabled={!proxmarkStatus.enabled || isProbing || identifyingTechnology !== null} onClick={() => void identifyCard("lf")}>
                      <RadioTower size={16} /> {identifyingTechnology === "lf" ? "Reading" : "LF 125 kHz"}
                    </button>
                  </div>
                  <div className="mt-2 flex gap-2">
                    <button type="button" className="btn btn-secondary flex-1" disabled={!proxmarkStatus.enabled || isProbing || identifyingTechnology !== null} onClick={() => void runProbe()}>
                      <Usb size={16} /> {isProbing ? "Probing" : "Probe"}
                    </button>
                    <button type="button" className="icon-button" onClick={() => void loadProxmarkStatus()} title="Refresh device status" aria-label="Refresh device status"><RefreshCw size={16} /></button>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </aside>
      </div>

      {(identifyResult || probeResult) ? (
        <section className="panel mt-5">
          <div className="panel-heading">
            <SectionHeader
              title={identifyResult ? "Latest identification" : "Latest device probe"}
              description={identifyResult ? "Parsed credential response and preserved command evidence." : "Device client response from the most recent readiness check."}
              action={<StatusBadge status={(identifyResult ?? probeResult)?.success ? "completed" : "failed"} />}
            />
          </div>
          <div className="panel-body grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
            <dl className="space-y-4 text-sm">
              <div><dt className="text-xs font-semibold text-slate-500">Command</dt><dd className="mono mt-1 break-all text-slate-900">{identifyResult?.command ?? probeResult?.command}</dd></div>
              {identifyResult ? <>
                <div><dt className="text-xs font-semibold text-slate-500">Credential</dt><dd className="mt-1 font-semibold text-slate-900">{identifyResult.card_type ?? "Not detected"}</dd></div>
                <div><dt className="text-xs font-semibold text-slate-500">Protocol</dt><dd className="mt-1 text-slate-900">{identifyResult.protocol ?? "Unknown"}</dd></div>
                <div><dt className="text-xs font-semibold text-slate-500">UID</dt><dd className="mono mt-1 break-all text-slate-900">{identifyResult.uid ?? "Unavailable"}</dd></div>
              </> : null}
            </dl>
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-bold text-slate-600"><SquareTerminal size={15} /> Raw client output</div>
              <pre className="terminal">{latestOutput || (identifyResult?.error ?? probeResult?.error) || "No output returned."}</pre>
            </div>
          </div>
        </section>
      ) : null}

      <section className="panel mt-5">
        <div className="panel-heading">
          <SectionHeader
            title="Credential intelligence"
            description="Observed credential profiles correlated against the local reference dataset."
            action={<button type="button" className="icon-button" onClick={() => void loadCardProfiles()} title="Refresh credential profiles" aria-label="Refresh credential profiles"><RefreshCw size={16} /></button>}
          />
        </div>
        {profileError ? <div className="m-4"><InlineAlert>{profileError}</InlineAlert></div> : null}
        {isLoadingProfiles ? (
          <LoadingState label="Correlating credential profiles" />
        ) : !profileReview || profileReview.profiles.length === 0 ? (
          <EmptyState title="No device observations yet" description="Use the identification controls or an assessment session to collect the first credential profile." />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead><tr><th>Credential</th><th>Technology</th><th>Attention</th><th>Observations</th><th>Dataset match</th><th>Last seen</th></tr></thead>
              <tbody>
                {profileReview.profiles.slice(0, 10).map((profile) => {
                  const match = profile.dataset_matches[0];
                  return (
                    <tr key={profile.profile_id}>
                      <td>
                        <div className="flex items-center gap-2 font-semibold text-slate-900"><Fingerprint size={15} className="text-teal-700" /> {profile.card_type ?? "Unknown credential"}</div>
                        <div className="mono mt-1 max-w-xs break-all text-xs text-slate-500">{profile.uid ?? "UID unavailable"}</div>
                      </td>
                      <td><span className="font-semibold uppercase text-slate-700">{profile.technology}</span><div className="mt-1 text-xs text-slate-500">{profile.protocol ?? "Unknown protocol"}</div></td>
                      <td><StatusBadge status={profile.attention_level} /></td>
                      <td className="mono">{profile.observation_count}</td>
                      <td>{match ? <><span className="font-semibold text-slate-900">{match.score}%</span><div className="mt-1 text-xs capitalize text-slate-500">{match.confidence} confidence</div></> : <span className="text-slate-500">No match</span>}</td>
                      <td className="whitespace-nowrap text-xs">{formatTimestamp(profile.last_seen)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="mt-5 flex items-start gap-3 border-l-2 border-amber-600 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <AlertTriangle size={18} className="mt-0.5 shrink-0" />
        <p className="m-0"><strong>Authorized use boundary:</strong> acquisition and analysis controls are intended for supervised assessment of owned or explicitly authorized credentials.</p>
      </div>
    </div>
  );
}
