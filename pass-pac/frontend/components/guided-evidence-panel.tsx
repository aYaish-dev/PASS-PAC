"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Compass,
  Play,
  ShieldCheck,
} from "lucide-react";

import type { GuidedEvidence } from "../lib/api";

type GuidedEvidencePanelProps = {
  guidance: GuidedEvidence;
  activeAction: string | null;
  onRunRecipe: (recipeKey: string, recommendationId: string) => Promise<void>;
  onOpenWorkspace: (workspace: string) => void;
};

const priorityStyles = {
  now: "border-[#e5b3a8] bg-[#fff2ef] text-[#8b3527]",
  next: "border-[#dfcf87] bg-[#fff9e4] text-[#715d13]",
  later: "border-[#b9c7d4] bg-[#f2f6f8] text-[#52616b]",
};

const policyStyles: Record<string, string> = {
  pass: "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]",
  fail: "border-[#e2a6a6] bg-[#fff0f0] text-[#9b2c2c]",
  insufficient_evidence: "border-[#d7c56d] bg-[#fff8dc] text-[#6d5a12]",
};

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function GuidedEvidencePanel({
  guidance,
  activeAction,
  onRunRecipe,
  onOpenWorkspace,
}: GuidedEvidencePanelProps) {
  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-lg border border-[#cbd6dc] bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-[#d8e0e5] px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[#1f6f61]">
              <Compass size={18} aria-hidden="true" />
              <p className="text-sm font-semibold uppercase">Guided evidence</p>
            </div>
            <h2 className="mt-2 text-xl font-semibold text-[#17202a]">
              Evidence acquisition queue
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-[#52616b]">
              Deterministic recommendations derived from credential evidence,
              experiment state, and the selected assurance policy.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            <span className="rounded-md border border-[#b8c9cf] bg-[#f3f8f8] px-2.5 py-1 text-[#2f6f73]">
              {guidance.engine_version}
            </span>
            <span className="rounded-md border border-[#cbd6dc] bg-[#f6f8f9] px-2.5 py-1 text-[#52616b]">
              Read-only registry
            </span>
          </div>
        </div>

        <div className="grid border-b border-[#d8e0e5] sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Evidence coverage",
              value: `${guidance.average_coverage_percent}%`,
              detail: `${guidance.card_count} credentials`,
            },
            {
              label: "Open evidence gaps",
              value: guidance.open_gap_count,
              detail: label(guidance.overall_status),
            },
            {
              label: "Critical paths",
              value: guidance.critical_path_count,
              detail: "Explicit failure indicators",
            },
            {
              label: "Ready actions",
              value: guidance.executable_recommendation_count,
              detail: "Registered recipes",
            },
          ].map((metric) => (
            <div
              key={metric.label}
              className="border-b border-[#d8e0e5] px-5 py-4 last:border-b-0 sm:nth-[2]:border-b-0 xl:border-b-0 xl:border-r xl:last:border-r-0"
            >
              <p className="text-xs font-semibold uppercase text-[#66757f]">
                {metric.label}
              </p>
              <p className="mt-2 text-2xl font-semibold text-[#17202a]">
                {metric.value}
              </p>
              <p className="mt-1 text-xs capitalize text-[#66757f]">
                {metric.detail}
              </p>
            </div>
          ))}
        </div>

        <div className="px-5 py-5">
          <div className="flex items-center justify-between gap-4">
            <h3 className="text-base font-semibold text-[#17202a]">
              Recommended sequence
            </h3>
            <span className="text-xs font-medium text-[#66757f]">
              {guidance.recommendations.length} actions
            </span>
          </div>

          <div className="mt-4 divide-y divide-[#dfe5e8] border-y border-[#dfe5e8]">
            {guidance.recommendations.map((recommendation) => {
              const actionKey = `guidance-${recommendation.id}`;
              const isRunning = activeAction === actionKey;
              return (
                <article
                  key={recommendation.id}
                  className="grid gap-4 py-5 lg:grid-cols-[40px_minmax(0,1fr)_auto] lg:items-start"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#cbd6dc] bg-[#f6f8f9] text-sm font-semibold text-[#2f6f73]">
                    {recommendation.rank}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="font-semibold text-[#17202a]">
                        {recommendation.title}
                      </h4>
                      <span
                        className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase ${priorityStyles[recommendation.priority]}`}
                      >
                        {recommendation.priority}
                      </span>
                      <span className="rounded-md border border-[#cbd6dc] bg-white px-2 py-0.5 text-[11px] font-medium capitalize text-[#52616b]">
                        {label(recommendation.safety_tier)}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[#52616b]">
                      {recommendation.rationale}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#52616b]">
                      <span className="font-semibold capitalize">
                        {recommendation.scope}
                      </span>
                      {recommendation.expected_evidence.map((item) => (
                        <span key={item} className="inline-flex items-center gap-1.5">
                          <CheckCircle2 size={13} aria-hidden="true" />
                          {item}
                        </span>
                      ))}
                    </div>
                    {recommendation.blocking_reason ? (
                      <p className="mt-3 inline-flex items-start gap-2 text-xs leading-5 text-[#806315]">
                        <CircleAlert size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                        {recommendation.blocking_reason}
                      </p>
                    ) : null}
                  </div>
                  <div className="lg:pt-0.5">
                    {recommendation.action_type === "recipe" && recommendation.recipe_key ? (
                      <button
                        type="button"
                        disabled={!recommendation.can_execute || isRunning}
                        onClick={() =>
                          void onRunRecipe(
                            recommendation.recipe_key as string,
                            recommendation.id,
                          )
                        }
                        className="inline-flex min-w-36 items-center justify-center gap-2 rounded-md bg-[#1f5d63] px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-[#184a4f] disabled:cursor-not-allowed disabled:bg-[#aab8bd]"
                      >
                        <Play size={15} aria-hidden="true" />
                        {isRunning ? "Running" : "Run recipe"}
                      </button>
                    ) : recommendation.href ? (
                      <Link
                        href={recommendation.href}
                        className="inline-flex min-w-36 items-center justify-center gap-2 rounded-md border border-[#9fb3bd] bg-white px-3.5 py-2 text-sm font-semibold text-[#234d5a] transition hover:bg-[#f0f5f6]"
                      >
                        Open workspace
                        <ArrowRight size={15} aria-hidden="true" />
                      </Link>
                    ) : recommendation.target_workspace ? (
                      <button
                        type="button"
                        onClick={() =>
                          onOpenWorkspace(recommendation.target_workspace as string)
                        }
                        className="inline-flex min-w-36 items-center justify-center gap-2 rounded-md border border-[#9fb3bd] bg-white px-3.5 py-2 text-sm font-semibold text-[#234d5a] transition hover:bg-[#f0f5f6]"
                      >
                        Review evidence
                        <ArrowRight size={15} aria-hidden="true" />
                      </button>
                    ) : (
                      <span className="inline-flex min-w-36 items-center justify-center gap-2 rounded-md border border-[#cbd6dc] bg-[#f6f8f9] px-3.5 py-2 text-sm font-semibold text-[#66757f]">
                        <ClipboardCheck size={15} aria-hidden="true" />
                        Manual evidence
                      </span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[#cbd6dc] bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-[#d8e0e5] px-5 py-4">
          <ShieldCheck size={18} className="text-[#2f6f73]" aria-hidden="true" />
          <h3 className="text-base font-semibold text-[#17202a]">
            Credential evidence coverage
          </h3>
        </div>
        {guidance.cards.length ? (
          <div className="divide-y divide-[#dfe5e8]">
            {guidance.cards.map((card) => (
              <div
                key={card.card_id}
                className="grid gap-4 px-5 py-4 md:grid-cols-[minmax(0,1fr)_120px_120px] md:items-center"
              >
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/cards/${card.card_id}`}
                      className="font-semibold text-[#234d5a] hover:underline"
                    >
                      {card.card_type}
                    </Link>
                    {card.critical_failure ? (
                      <span className="rounded-md border border-[#e2a6a6] bg-[#fff0f0] px-2 py-0.5 text-[11px] font-semibold uppercase text-[#9b2c2c]">
                        Critical path
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-[#66757f]">
                    Card {card.card_id} · {card.technology} · {card.evidence_gaps.length} gaps
                  </p>
                  {card.evidence_gaps.length ? (
                    <p className="mt-2 text-xs leading-5 text-[#52616b]">
                      {card.evidence_gaps.map((gap) => gap.criterion_name).join(" · ")}
                    </p>
                  ) : null}
                </div>
                <div>
                  <p className="text-xs font-medium text-[#66757f]">Score range</p>
                  <p className="mt-1 font-semibold text-[#17202a]">
                    {card.score === null ? "Unknown" : card.score.toFixed(1)} / 10
                    <span className="ml-1 text-xs font-normal text-[#66757f]">
                      ({card.score_lower_bound}-{card.score_upper_bound})
                    </span>
                  </p>
                </div>
                <div className="md:text-right">
                  <span
                    className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold capitalize ${
                      policyStyles[card.policy_status] ??
                      "border-[#b7c3cc] bg-[#f4f6f7] text-[#52616b]"
                    }`}
                  >
                    {label(card.policy_status)} · {card.coverage_percent}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-5 py-10 text-center text-sm text-[#66757f]">
            No credential evidence has been recorded for this session.
          </div>
        )}
      </section>
    </div>
  );
}
