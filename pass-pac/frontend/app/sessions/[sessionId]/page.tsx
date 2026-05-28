"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  deleteSession,
  getSession,
  listSessionCards,
  listSessionFindings,
  simulateSessionScan,
  startSession,
  stopSession,
} from "../../../lib/api";
import type { DetectedCard, Finding, ScanSession } from "../../../lib/api";

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

export default function SessionDetailsPage() {
  const params = useParams<{ sessionId?: string | string[] }>();
  const router = useRouter();
  const sessionId = resolveSessionId(params.sessionId);

  const [session, setSession] = useState<ScanSession | null>(null);
  const [cards, setCards] = useState<DetectedCard[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [technology, setTechnology] = useState("");
  const [cardType, setCardType] = useState("");
  const [source, setSource] = useState("");
  const [dataset, setDataset] = useState("");
  const [fileType, setFileType] = useState("");
  const [uidFilter, setUidFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshSession() {
    if (sessionId === null) {
      setError("Invalid session id.");
      setIsLoading(false);
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      const [sessionData, cardData, findingData] = await Promise.all([
        getSession(sessionId),
        listSessionCards(sessionId),
        listSessionFindings(sessionId),
      ]);
      setSession(sessionData);
      setCards(cardData);
      setFindings(findingData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load session.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshSession();
  }, [sessionId]);

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

  const latestCard = cards[0];
  const highRiskCount = findings.filter((finding) =>
    ["high", "critical"].includes(finding.risk_level),
  ).length;
  const cardLabelById = new Map(
    cards.map((card) => [card.id, `${card.card_type} ${card.uid}`] as const),
  );

  return (
    <main className="min-h-screen bg-[#f6f7f9]">
      <section className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 lg:px-10">
        <header className="flex flex-col gap-4 border-b border-[#d8dde3] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase text-[#2f6f73]">
              Operator panel
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-[#17202a] sm:text-4xl">
              {session?.session_name ?? "Session Details"}
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/sessions"
              className="inline-flex items-center justify-center rounded-md border border-[#b7c3cc] bg-white px-4 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
            >
              Sessions
            </Link>
            <Link
              href="/"
              className="inline-flex items-center justify-center rounded-md border border-[#b7c3cc] bg-white px-4 py-2 text-sm font-semibold text-[#36454f] transition hover:bg-[#f0f3f5] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
            >
              Dashboard
            </Link>
          </div>
        </header>

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
          <div className="grid gap-5 py-8 lg:grid-cols-[360px_1fr]">
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

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
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

            <section className="space-y-5">
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

              <section className="rounded-lg border border-[#d8dde3] bg-white shadow-sm">
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

              <section className="rounded-lg border border-[#d8dde3] bg-white shadow-sm">
                <div className="border-b border-[#edf0f2] p-5">
                  <h2 className="text-lg font-semibold text-[#17202a]">
                    Risk Findings
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] border-collapse text-left text-sm">
                    <thead className="bg-[#fafbfc] text-xs uppercase text-[#52616b]">
                      <tr>
                        <th className="px-5 py-3 font-semibold">Finding</th>
                        <th className="px-5 py-3 font-semibold">Risk</th>
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
                            colSpan={5}
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

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Latest Raw Evidence
                </h2>
                <pre className="mt-5 max-h-80 overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                  {latestCard
                    ? JSON.stringify(latestCard.normalized_data_json, null, 2)
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
