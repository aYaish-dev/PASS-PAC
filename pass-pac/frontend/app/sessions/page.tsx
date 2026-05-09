"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  createSession,
  deleteSession,
  listSessions,
  startSession,
  stopSession,
} from "../../lib/api";
import type { ScanSession } from "../../lib/api";

const statusStyles: Record<string, string> = {
  created: "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]",
  running: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
  completed: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
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

export default function SessionsPage() {
  const [sessions, setSessions] = useState<ScanSession[]>([]);
  const [sessionName, setSessionName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState("simulator");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshSessions() {
    setError(null);
    setIsLoading(true);
    try {
      const data = await listSessions();
      setSessions(data);
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
      await createSession({
        session_name: trimmedName,
        description: description.trim() || null,
        mode,
        environment: "local",
      });
      setSessionName("");
      setDescription("");
      setMode("simulator");
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create session.");
    } finally {
      setIsCreating(false);
    }
  }

  async function runSessionAction(
    actionKey: string,
    action: () => Promise<ScanSession | void>,
  ) {
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

  return (
    <main className="min-h-screen bg-[#f6f7f9]">
      <section className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 lg:px-10">
        <header className="flex flex-col gap-4 border-b border-[#d8dde3] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#2f6f73]">
              Local session control
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-[#17202a] sm:text-4xl">
              Sessions
            </h1>
          </div>
          <Link
            href="/"
            className="inline-flex w-fit items-center justify-center rounded-md border border-[#b7c3cc] bg-white px-4 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
          >
            Dashboard
          </Link>
        </header>

        <div className="grid gap-5 py-8 lg:grid-cols-[360px_1fr]">
          <form
            onSubmit={handleCreate}
            className="h-fit rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm"
          >
            <h2 className="text-lg font-semibold text-[#17202a]">
              Create Session
            </h2>

            <label className="mt-5 block text-sm font-medium text-[#36454f]">
              Session name
              <input
                value={sessionName}
                onChange={(event) => setSessionName(event.target.value)}
                className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                maxLength={120}
                placeholder="Lobby baseline assessment"
              />
            </label>

            <label className="mt-4 block text-sm font-medium text-[#36454f]">
              Description
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="mt-2 min-h-28 w-full resize-y rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
                maxLength={1000}
                placeholder="Authorized local assessment"
              />
            </label>

            <label className="mt-4 block text-sm font-medium text-[#36454f]">
              Mode
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                className="mt-2 w-full rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm text-[#17202a] outline-none transition focus:border-[#2f6f73] focus:ring-2 focus:ring-[#cfe7e5]"
              >
                <option value="simulator">Simulator</option>
              </select>
            </label>

            <button
              type="submit"
              disabled={isCreating}
              className="mt-5 inline-flex w-full items-center justify-center rounded-md bg-[#2f6f73] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#255b5f] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#8daaad]"
            >
              {isCreating ? "Creating..." : "Create Session"}
            </button>
          </form>

          <section className="rounded-lg border border-[#d8dde3] bg-white shadow-sm">
            <div className="flex flex-col gap-3 border-b border-[#edf0f2] p-5 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-semibold text-[#17202a]">
                Session Table
              </h2>
              <button
                type="button"
                onClick={() => void refreshSessions()}
                disabled={isLoading}
                className="inline-flex w-fit items-center justify-center rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-[#8a969e]"
              >
                Refresh
              </button>
            </div>

            {error ? (
              <div className="mx-5 mt-5 rounded-md border border-[#e6b8b8] bg-[#fff4f4] px-4 py-3 text-sm font-medium text-[#9b2c2c]">
                {error}
              </div>
            ) : null}

            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] border-collapse text-left text-sm">
                <thead className="bg-[#fafbfc] text-xs uppercase tracking-[0.08em] text-[#52616b]">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Name</th>
                    <th className="px-5 py-3 font-semibold">Mode</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Started</th>
                    <th className="px-5 py-3 font-semibold">Ended</th>
                    <th className="px-5 py-3 font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#edf0f2]">
                  {isLoading ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-5 py-10 text-center font-medium text-[#6b7780]"
                      >
                        Loading sessions...
                      </td>
                    </tr>
                  ) : sessions.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-5 py-10 text-center font-medium text-[#6b7780]"
                      >
                        No sessions yet
                      </td>
                    </tr>
                  ) : (
                    sessions.map((session) => (
                      <tr key={session.id} className="align-top">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-[#17202a]">
                            {session.session_name}
                          </div>
                          <div className="mt-1 max-w-72 text-[#6b7780]">
                            {session.description || "-"}
                          </div>
                        </td>
                        <td className="px-5 py-4 capitalize text-[#36454f]">
                          {session.mode}
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                              statusStyles[session.status] ??
                              "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                            }`}
                          >
                            {session.status}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-[#36454f]">
                          {formatDate(session.started_at)}
                        </td>
                        <td className="px-5 py-4 text-[#36454f]">
                          {formatDate(session.ended_at)}
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={
                                session.status !== "created" ||
                                activeAction === `start-${session.id}`
                              }
                              onClick={() =>
                                void runSessionAction(`start-${session.id}`, () =>
                                  startSession(session.id),
                                )
                              }
                              className="rounded-md border border-[#9ac2b8] bg-[#e8f5f2] px-3 py-1.5 text-xs font-semibold text-[#1f6f61] transition hover:bg-[#d8eee9] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                            >
                              Start
                            </button>
                            <button
                              type="button"
                              disabled={
                                session.status !== "running" ||
                                activeAction === `stop-${session.id}`
                              }
                              onClick={() =>
                                void runSessionAction(`stop-${session.id}`, () =>
                                  stopSession(session.id),
                                )
                              }
                              className="rounded-md border border-[#b8c4d6] bg-[#eef3fa] px-3 py-1.5 text-xs font-semibold text-[#315a8a] transition hover:bg-[#e1ebf8] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                            >
                              Stop
                            </button>
                            <button
                              type="button"
                              disabled={activeAction === `delete-${session.id}`}
                              onClick={() =>
                                void runSessionAction(
                                  `delete-${session.id}`,
                                  () => deleteSession(session.id),
                                )
                              }
                              className="rounded-md border border-[#e6b8b8] bg-[#fff4f4] px-3 py-1.5 text-xs font-semibold text-[#9b2c2c] transition hover:bg-[#ffe8e8] disabled:cursor-not-allowed disabled:border-[#d5dddc] disabled:bg-[#f4f6f7] disabled:text-[#9aa5ab]"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
