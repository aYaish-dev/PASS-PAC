"use client";

import {
  ArrowRight,
  CalendarClock,
  CircleStop,
  Plus,
  Play,
  RefreshCw,
  ScanLine,
  Search,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EmptyState, InlineAlert, LoadingState, PageHeader, SectionHeader, StatusBadge } from "../../components/ui";
import {
  createSession,
  deleteSession,
  listSessionCards,
  listSessions,
  simulateSessionScan,
  startSession,
  stopSession,
} from "../../lib/api";
import type { DetectedCard, ScanSession } from "../../lib/api";

function formatDate(value: string | null) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<ScanSession[]>([]);
  const [cardsBySession, setCardsBySession] = useState<Record<number, DetectedCard[]>>({});
  const [sessionName, setSessionName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState("simulator");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filteredSessions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return sessions.filter((session) => {
      const matchesStatus = filter === "all" || session.status === filter;
      const matchesQuery = !normalized || session.session_name.toLowerCase().includes(normalized) || (session.description ?? "").toLowerCase().includes(normalized);
      return matchesStatus && matchesQuery;
    });
  }, [filter, query, sessions]);

  async function refreshSessions() {
    setError(null);
    setIsLoading(true);
    try {
      const data = await listSessions();
      setSessions(data);
      const cardPairs = await Promise.all(data.map(async (session) => [session.id, await listSessionCards(session.id)] as const));
      setCardsBySession(Object.fromEntries(cardPairs));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sessions.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshSessions();
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = sessionName.trim();
    if (!trimmedName) {
      setError("Session name is required.");
      return;
    }

    setIsCreating(true);
    setError(null);
    try {
      await createSession({ session_name: trimmedName, description: description.trim() || null, mode, environment: "local" });
      setSessionName("");
      setDescription("");
      setMode("simulator");
      setShowCreate(false);
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create session.");
    } finally {
      setIsCreating(false);
    }
  }

  async function runSessionAction(actionKey: string, action: () => Promise<ScanSession | DetectedCard | void>) {
    setActiveAction(actionKey);
    setError(null);
    try {
      await action();
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update session.");
    } finally {
      setActiveAction(null);
    }
  }

  function confirmDelete(session: ScanSession) {
    if (!window.confirm(`Delete "${session.session_name}" and its session record?`)) return;
    void runSessionAction(`delete-${session.id}`, () => deleteSession(session.id));
  }

  const counts = {
    all: sessions.length,
    created: sessions.filter((session) => session.status === "created").length,
    running: sessions.filter((session) => session.status === "running").length,
    completed: sessions.filter((session) => session.status === "completed").length,
  };

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Assessment lifecycle"
        title="Sessions"
        description="Define scope, control acquisition state, and preserve each authorized assessment as a separate evidence boundary."
        actions={
          <>
            <button type="button" className="icon-button" onClick={() => void refreshSessions()} disabled={isLoading} title="Refresh sessions" aria-label="Refresh sessions"><RefreshCw size={17} /></button>
            <button type="button" className="btn btn-primary" onClick={() => setShowCreate((visible) => !visible)} aria-expanded={showCreate}>
              <Plus size={16} /> Create session
            </button>
          </>
        }
      />

      {error ? <div className="mb-5"><InlineAlert>{error}</InlineAlert></div> : null}

      {showCreate ? (
        <section className="panel mb-5">
          <div className="panel-heading">
            <SectionHeader title="New assessment session" description="Create the record first; acquisition begins only after the session is started." />
          </div>
          <form onSubmit={handleCreate} className="panel-body grid gap-4 lg:grid-cols-[minmax(220px,1fr)_minmax(320px,1.5fr)_250px_auto] lg:items-end">
            <label className="field-label">Session name
              <input className="field-control" value={sessionName} onChange={(event) => setSessionName(event.target.value)} maxLength={120} placeholder="North entrance baseline" autoFocus />
            </label>
            <label className="field-label">Description
              <input className="field-control" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={1000} placeholder="Authorized reader and credential assessment" />
            </label>
            <label className="field-label">Acquisition mode
              <select className="field-control" value={mode} onChange={(event) => setMode(event.target.value)}>
                <option value="simulator">Simulator</option>
                <option value="proxmark">Proxmark automated assessment</option>
              </select>
            </label>
            <div className="flex gap-2">
              <button type="submit" className="btn btn-teal" disabled={isCreating}>{isCreating ? "Creating" : "Create"}</button>
              <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-heading space-y-4">
          <SectionHeader title="Assessment register" description={`${sessions.length} sessions with ${Object.values(cardsBySession).reduce((sum, group) => sum + group.length, 0)} credential observations.`} />
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="workspace-tabs session-filters" role="tablist" aria-label="Filter sessions by status">
              {(["all", "created", "running", "completed"] as const).map((status) => (
                <button key={status} type="button" role="tab" aria-selected={filter === status} onClick={() => setFilter(status)} className={`workspace-tab ${filter === status ? "workspace-tab-active" : ""}`}>
                  <span className="capitalize">{status}</span><span className="mono text-[11px]">{counts[status]}</span>
                </button>
              ))}
            </div>
            <label className="relative block w-full lg:w-72">
              <span className="sr-only">Search sessions</span>
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} className="field-control search-control mt-0" placeholder="Search sessions" />
            </label>
          </div>
        </div>

        {isLoading ? (
          <LoadingState label="Loading assessment sessions" />
        ) : filteredSessions.length === 0 ? (
          <EmptyState
            title={sessions.length === 0 ? "No sessions recorded" : "No sessions match this view"}
            description={sessions.length === 0 ? "Create the first authorized assessment session to begin." : "Change the status filter or search terms."}
            action={sessions.length === 0 ? <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}><Plus size={16} /> Create session</button> : undefined}
          />
        ) : (
          <>
            <div className="hidden data-table-wrap md:block">
              <table className="data-table min-w-[980px]">
                <thead><tr><th>Session</th><th>Status</th><th>Mode</th><th>Credentials</th><th>Timing</th><th className="text-right">Controls</th></tr></thead>
                <tbody>
                  {filteredSessions.map((session) => {
                    const sessionCards = cardsBySession[session.id] ?? [];
                    return (
                      <tr key={session.id}>
                        <td>
                          <Link href={`/sessions/${session.id}`} className="font-semibold text-slate-900 hover:text-teal-700">{session.session_name}</Link>
                          <div className="mt-1 max-w-sm truncate text-xs text-slate-500">{session.description || "No description"}</div>
                        </td>
                        <td><StatusBadge status={session.status} /></td>
                        <td className="capitalize">{session.mode}</td>
                        <td><span className="mono font-semibold text-slate-900">{sessionCards.length}</span>{sessionCards[0] ? <div className="mono mt-1 max-w-40 truncate text-xs text-slate-500">{sessionCards[0].uid}</div> : null}</td>
                        <td><div className="text-xs"><span className="font-semibold text-slate-700">Start</span> {formatDate(session.started_at)}</div><div className="mt-1 text-xs"><span className="font-semibold text-slate-700">End</span> {formatDate(session.ended_at)}</div></td>
                        <td>
                          <div className="flex justify-end gap-1">
                            <button type="button" className="icon-button" disabled={session.status !== "created" || activeAction === `start-${session.id}`} onClick={() => void runSessionAction(`start-${session.id}`, () => startSession(session.id))} title="Start session" aria-label={`Start ${session.session_name}`}><Play size={16} /></button>
                            {session.mode === "simulator" ? <button type="button" className="icon-button" disabled={session.status !== "running" || activeAction === `scan-${session.id}`} onClick={() => void runSessionAction(`scan-${session.id}`, () => simulateSessionScan(session.id))} title="Run simulator scan" aria-label={`Scan in ${session.session_name}`}><ScanLine size={16} /></button> : null}
                            <button type="button" className="icon-button" disabled={session.status !== "running" || activeAction === `stop-${session.id}`} onClick={() => void runSessionAction(`stop-${session.id}`, () => stopSession(session.id))} title="Stop session" aria-label={`Stop ${session.session_name}`}><CircleStop size={16} /></button>
                            <Link href={`/sessions/${session.id}`} className="icon-button" title="Open operator panel" aria-label={`Open ${session.session_name}`}><ArrowRight size={16} /></Link>
                            <button type="button" className="icon-button text-red-700" disabled={activeAction === `delete-${session.id}`} onClick={() => confirmDelete(session)} title="Delete session" aria-label={`Delete ${session.session_name}`}><Trash2 size={16} /></button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-slate-200 md:hidden">
              {filteredSessions.map((session) => (
                <article key={session.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0"><Link href={`/sessions/${session.id}`} className="font-semibold text-slate-900">{session.session_name}</Link><p className="mt-1 truncate text-xs text-slate-500">{session.description || "No description"}</p></div>
                    <StatusBadge status={session.status} />
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs"><div><span className="block font-semibold text-slate-500">Mode</span><span className="mt-1 block capitalize text-slate-900">{session.mode}</span></div><div><span className="block font-semibold text-slate-500">Credentials</span><span className="mono mt-1 block text-slate-900">{(cardsBySession[session.id] ?? []).length}</span></div></div>
                  <div className="mt-4 flex gap-2">
                    <Link href={`/sessions/${session.id}`} className="btn btn-primary flex-1">Open <ArrowRight size={15} /></Link>
                    <button type="button" className="icon-button text-red-700" onClick={() => confirmDelete(session)} title="Delete session" aria-label={`Delete ${session.session_name}`}><Trash2 size={16} /></button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </section>

      <div className="mt-4 flex items-center gap-2 text-xs text-slate-500"><CalendarClock size={14} /> Session timestamps use the browser&apos;s local timezone.</div>
    </div>
  );
}
