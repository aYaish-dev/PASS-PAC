"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getCard, getSession, listCardFindings } from "../../../lib/api";
import type { DetectedCard, Finding, ScanSession } from "../../../lib/api";

const riskStyles: Record<string, string> = {
  informational: "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]",
  low: "border-[#b8c4d6] bg-[#eef3fa] text-[#315a8a]",
  medium: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
  high: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  critical: "border-[#c98b8b] bg-[#ffe5e5] text-[#7f1d1d]",
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

function resolveCardId(value: string | string[] | undefined) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  const parsedValue = Number(rawValue);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

export default function CardDetailsPage() {
  const params = useParams<{ cardId?: string | string[] }>();
  const cardId = resolveCardId(params.cardId);

  const [card, setCard] = useState<DetectedCard | null>(null);
  const [session, setSession] = useState<ScanSession | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        const [sessionData, findingData] = await Promise.all([
          getSession(cardData.session_id),
          listCardFindings(cardId),
        ]);
        setSession(sessionData);
        setFindings(findingData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load card.");
      } finally {
        setIsLoading(false);
      }
    }

    void loadCard();
  }, [cardId]);

  const primaryFinding = findings[0];

  return (
    <main className="min-h-screen bg-[#f6f7f9]">
      <section className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 lg:px-10">
        <header className="flex flex-col gap-4 border-b border-[#d8dde3] pb-6 sm:flex-row sm:items-end sm:justify-between">
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
          <div className="grid gap-5 py-8 lg:grid-cols-[380px_1fr]">
            <aside className="space-y-5">
              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-lg font-semibold text-[#17202a]">
                    Credential
                  </h2>
                  <span
                    className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                      riskStyles[card.risk_level] ??
                      "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                    }`}
                  >
                    {card.risk_level}
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
                        className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                          riskStyles[primaryFinding.risk_level] ??
                          "border-[#b7c3cc] bg-[#f4f6f7] text-[#36454f]"
                        }`}
                      >
                        {primaryFinding.risk_level}
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

            <section className="space-y-5">
              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
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
                        className="rounded-md border border-[#edf0f2] p-4"
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
                        <pre className="mt-4 max-h-72 overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                          {JSON.stringify(finding.evidence_json, null, 2)}
                        </pre>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Normalized Data
                </h2>
                <pre className="mt-5 max-h-[440px] overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
                  {JSON.stringify(card.normalized_data_json, null, 2)}
                </pre>
              </section>

              <section className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-[#17202a]">
                  Raw Output
                </h2>
                <pre className="mt-5 max-h-80 overflow-auto rounded-md border border-[#d8dde3] bg-[#111827] p-4 text-xs leading-6 text-[#f8fafc]">
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
