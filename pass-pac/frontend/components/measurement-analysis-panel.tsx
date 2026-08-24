"use client";

import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  FileSpreadsheet,
  Info,
  ShieldCheck,
} from "lucide-react";
import type {
  MeasurementAnalysis,
  ProportionStatistics,
  SessionAssurance,
} from "../lib/api";

type MeasurementAnalysisPanelProps = {
  analysis: MeasurementAnalysis | null;
  assurance: SessionAssurance | null;
  exporting: boolean;
  onExportAnalysis: () => void;
};

function formatRate(value: ProportionStatistics) {
  return `${value.rate_percent.toFixed(1)}% (${value.events}/${value.attempts})`;
}

function formatInterval(value: ProportionStatistics) {
  return `${value.ci_lower_percent.toFixed(1)}-${value.ci_upper_percent.toFixed(1)}%`;
}

function formatTiming(value: number | null) {
  return value === null ? "-" : `${value.toLocaleString()} ms`;
}

function statusStyle(status: string) {
  if (status === "pass") return "border-[#9ac2b8] bg-[#e8f5f2] text-[#1f6f61]";
  if (status === "fail") return "border-[#e6b8b8] bg-[#fff4f4] text-[#9b2c2c]";
  return "border-[#e6cf9a] bg-[#fff9e8] text-[#8a5a00]";
}

export function MeasurementAnalysisPanel({
  analysis,
  assurance,
  exporting,
  onExportAnalysis,
}: MeasurementAnalysisPanelProps) {
  if (!analysis) {
    return (
      <div className="py-16 text-center text-sm font-medium text-[#6b7780]">
        Statistical analysis is unavailable.
      </div>
    );
  }

  const aliasByCardId = new Map(
    analysis.credentials
      .filter((item) => item.source_card_id !== null)
      .map((item) => [item.source_card_id as number, item.credential_alias]),
  );

  return (
    <div className="space-y-10 py-8">
      <section aria-labelledby="analysis-heading">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-[#2f6f73]">
              Baseline statistical analysis
            </p>
            <h2 id="analysis-heading" className="mt-2 text-xl font-semibold text-[#17202a]">
              Credential Performance
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#52616b]">
              Detection and correct identification are reported separately. Intervals quantify
              uncertainty for this controlled setup and are not population-wide claims.
            </p>
          </div>
          <button
            type="button"
            onClick={onExportAnalysis}
            disabled={exporting}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-[#315a8a] bg-white px-4 py-2 text-sm font-semibold text-[#315a8a] transition hover:bg-[#eef3fa] disabled:text-[#9ba9ba]"
          >
            <FileSpreadsheet size={17} aria-hidden="true" />
            {exporting ? "Exporting..." : "Export analysis CSV"}
          </button>
        </div>

        <div className="mt-5 grid gap-px overflow-hidden rounded-md border border-[#d8dde3] bg-[#d8dde3] sm:grid-cols-4">
          {[
            ["Analysis", analysis.analysis_version],
            ["Interval", `${analysis.interval_method}, ${analysis.confidence_level_percent}%`],
            ["Minimum repeats", `${analysis.minimum_attempts_per_condition} per condition`],
            ["Dataset", `${analysis.trial_count} trials / ${analysis.condition_count} conditions`],
          ].map(([label, value]) => (
            <div key={label} className="bg-white px-4 py-4">
              <p className="text-xs font-semibold uppercase text-[#6b7780]">{label}</p>
              <p className="mt-2 text-sm font-semibold text-[#17202a]">{value}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 overflow-x-auto rounded-md border border-[#d8dde3] bg-white">
          <table className="w-full min-w-[1040px] text-left text-sm">
            <thead className="bg-[#eef3f4] text-xs uppercase text-[#52616b]">
              <tr>
                <th className="px-4 py-3">Credential</th>
                <th className="px-4 py-3">Trials</th>
                <th className="px-4 py-3">Detection</th>
                <th className="px-4 py-3">Correct ID</th>
                <th className="px-4 py-3">Reliable ID range</th>
                <th className="px-4 py-3">Correct-ID timing</th>
                <th className="px-4 py-3">Partial responses</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf0f2]">
              {analysis.credentials.map((credential) => (
                <tr key={credential.credential_alias}>
                  <td className="px-4 py-3">
                    <p className="font-semibold text-[#17202a]">{credential.credential_alias}</p>
                    <p className="mt-1 text-xs text-[#6b7780]">
                      {credential.card_family ?? credential.technology_family}
                    </p>
                  </td>
                  <td className="px-4 py-3">{credential.trial_count}</td>
                  <td className="px-4 py-3">
                    <p className="font-semibold">{formatRate(credential.detection)}</p>
                    <p className="mt-1 text-xs text-[#6b7780]">95% CI {formatInterval(credential.detection)}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-semibold">{formatRate(credential.correct_identification)}</p>
                    <p className="mt-1 text-xs text-[#6b7780]">95% CI {formatInterval(credential.correct_identification)}</p>
                  </td>
                  <td className="px-4 py-3 font-semibold text-[#1f6f61]">
                    {credential.reliable_identification_distance_cm === null
                      ? "Not established"
                      : `${credential.reliable_identification_distance_cm} cm`}
                  </td>
                  <td className="px-4 py-3">
                    <p>{formatTiming(credential.correct_identification_timing.median_ms)} median</p>
                    <p className="mt-1 text-xs text-[#6b7780]">
                      IQR {formatTiming(credential.correct_identification_timing.q1_ms)} to {formatTiming(credential.correct_identification_timing.q3_ms)}
                    </p>
                  </td>
                  <td className="px-4 py-3">{credential.partial_response_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-t border-[#d8dde3] pt-8" aria-labelledby="distance-heading">
        <div className="flex items-start gap-3">
          <BarChart3 className="mt-0.5 text-[#315a8a]" size={20} aria-hidden="true" />
          <div>
            <h2 id="distance-heading" className="text-xl font-semibold text-[#17202a]">
              Performance by Distance
            </h2>
            <p className="mt-2 text-sm text-[#52616b]">
              Navy shows any protocol detection. Teal shows correct credential identification.
            </p>
          </div>
        </div>

        <div className="mt-6 space-y-8">
          {analysis.credentials.map((credential) => {
            const conditions = analysis.conditions.filter(
              (item) => item.credential_alias === credential.credential_alias,
            );
            return (
              <div key={credential.credential_alias}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-semibold text-[#17202a]">{credential.credential_alias}</h3>
                  <p className="text-xs text-[#6b7780]">{credential.card_family ?? credential.technology_family}</p>
                </div>
                <div className="mt-3 overflow-x-auto rounded-md border border-[#d8dde3] bg-white">
                  <div className="min-w-[720px] divide-y divide-[#edf0f2]">
                    {conditions.map((condition) => (
                      <div key={`${condition.distance_cm}-${condition.orientation}-${condition.presented_face}`} className="grid grid-cols-[90px_1fr_210px] items-center gap-4 px-4 py-3">
                        <div>
                          <p className="font-semibold text-[#17202a]">{condition.distance_cm} cm</p>
                          <p className="mt-1 text-xs capitalize text-[#6b7780]">{condition.orientation}</p>
                        </div>
                        <div className="space-y-2" aria-label={`${credential.credential_alias} at ${condition.distance_cm} centimeters`}>
                          <div className="h-3 overflow-hidden rounded-sm bg-[#e9eef3]">
                            <div className="h-full bg-[#315a8a]" style={{ width: `${condition.detection.rate_percent}%` }} />
                          </div>
                          <div className="h-3 overflow-hidden rounded-sm bg-[#e5efed]">
                            <div className="h-full bg-[#1f6f61]" style={{ width: `${condition.correct_identification.rate_percent}%` }} />
                          </div>
                        </div>
                        <div className="text-xs">
                          <p><span className="font-semibold text-[#315a8a]">Detected:</span> {formatRate(condition.detection)}</p>
                          <p className="mt-1"><span className="font-semibold text-[#1f6f61]">Correct:</span> {formatRate(condition.correct_identification)}</p>
                          <p className="mt-1 text-[#6b7780]">Correct 95% CI {formatInterval(condition.correct_identification)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-t border-[#d8dde3] pt-8" aria-labelledby="assurance-heading">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 text-[#1f6f61]" size={20} aria-hidden="true" />
          <div>
            <h2 id="assurance-heading" className="text-xl font-semibold text-[#17202a]">
              Access Path Security Score
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#52616b]">
              Version 2 scores five evidence-based controls on a 0-10 scale. Unknown controls
              reduce coverage and widen the score range; RF range never adds security points.
            </p>
          </div>
        </div>

        {assurance ? (
          <>
            <div className="mt-5 grid gap-px overflow-hidden rounded-md border border-[#d8dde3] bg-[#d8dde3] sm:grid-cols-4">
              {[
                ["Policy", assurance.policy.name],
                ["Average provisional score", assurance.average_score === null ? "Not calculable" : `${assurance.average_score}/10`],
                ["Insufficient evidence", `${assurance.insufficient_evidence_count} of ${assurance.card_count}`],
                ["Critical failures", assurance.critical_failure_count],
              ].map(([label, value]) => (
                <div key={label} className="bg-white px-4 py-4">
                  <p className="text-xs font-semibold uppercase text-[#6b7780]">{label}</p>
                  <p className="mt-2 text-lg font-semibold text-[#17202a]">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 overflow-x-auto rounded-md border border-[#d8dde3] bg-white">
              <table className="w-full min-w-[780px] text-left text-sm">
                <thead className="bg-[#eef3f4] text-xs uppercase text-[#52616b]">
                  <tr><th className="px-4 py-3">Credential</th><th className="px-4 py-3">Provisional score</th><th className="px-4 py-3">Evidence range</th><th className="px-4 py-3">Coverage</th><th className="px-4 py-3">Policy result</th><th className="px-4 py-3">Critical</th></tr>
                </thead>
                <tbody className="divide-y divide-[#edf0f2]">
                  {assurance.cards.map((card) => (
                    <tr key={card.card_id}>
                      <td className="px-4 py-3"><p className="font-semibold">{aliasByCardId.get(card.card_id) ?? `Card ${card.card_id}`}</p><p className="mt-1 text-xs text-[#6b7780]">{card.card_type}</p></td>
                      <td className="px-4 py-3 font-semibold">{card.score === null ? "Not calculable" : `${card.score}/10`}</td>
                      <td className="px-4 py-3">{card.score_lower_bound}-{card.score_upper_bound}/10</td>
                      <td className="px-4 py-3">{card.coverage_percent}%</td>
                      <td className="px-4 py-3"><span className={`rounded-md border px-2 py-1 text-xs font-semibold ${statusStyle(card.policy_status)}`}>{card.policy_status.replace("_", " ")}</span></td>
                      <td className="px-4 py-3">{card.critical_failure ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="mt-5 text-sm text-[#6b7780]">Security assurance data is unavailable.</p>
        )}
      </section>

      <section className="grid gap-8 border-t border-[#d8dde3] pt-8 lg:grid-cols-2">
        <div>
          <h2 className="text-xl font-semibold text-[#17202a]">Data Quality Flags</h2>
          <div className="mt-4 divide-y divide-[#edf0f2] rounded-md border border-[#d8dde3] bg-white">
            {analysis.quality_flags.map((flag) => {
              const Icon = flag.severity === "info" ? Info : AlertTriangle;
              return (
                <div key={flag.id} className="flex gap-3 px-4 py-4">
                  <Icon size={18} className={flag.severity === "high" ? "text-[#9b2c2c]" : flag.severity === "warning" ? "text-[#8a5a00]" : "text-[#315a8a]"} aria-hidden="true" />
                  <div><p className="font-semibold text-[#17202a]">{flag.title}</p><p className="mt-1 text-sm leading-6 text-[#52616b]">{flag.detail}</p></div>
                </div>
              );
            })}
            {!analysis.quality_flags.length ? <div className="flex gap-3 px-4 py-4"><CheckCircle2 size={18} className="text-[#1f6f61]" /><p className="text-sm font-medium text-[#1f6f61]">No automated quality warnings were identified.</p></div> : null}
          </div>
        </div>
        <div>
          <h2 className="text-xl font-semibold text-[#17202a]">Interpretation Boundaries</h2>
          <ol className="mt-4 divide-y divide-[#edf0f2] rounded-md border border-[#d8dde3] bg-white">
            {analysis.interpretation.map((item, index) => (
              <li key={item} className="grid grid-cols-[28px_1fr] gap-3 px-4 py-4 text-sm leading-6 text-[#52616b]">
                <span className="font-semibold text-[#2f6f73]">{index + 1}</span><span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}
