"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AuthGuard from "@/components/layout/AuthGuard";
import { runs as runsApi, RunResponse, ExperimentResultResponse } from "@/lib/api";

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <span className="text-green-500 text-xl">✓</span>;
  if (status === "failed") return <span className="text-red-500 text-xl">✗</span>;
  return <div className="w-5 h-5 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin inline-block" />;
}

function MetricsTable({ results }: { results: ExperimentResultResponse[] }) {
  const modelNames = [...new Set(results.map((r) => r.model_name))];
  const allMetrics = [...new Set(results.flatMap((r) => Object.keys(r.metrics)))];

  return (
    <div className="space-y-6">
      {modelNames.map((model) => {
        const modelResults = results.filter((r) => r.model_name === model);
        const importances = modelResults.find((r) => r.feature_importances)?.feature_importances;

        return (
          <div key={model} className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
              <span className="font-medium text-sm">{model}</span>
            </div>

            {/* Metrics table */}
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Split</th>
                    {allMetrics.map((m) => (
                      <th key={m} className="px-4 py-2 text-left text-xs font-medium text-gray-500">{m}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {modelResults.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-700">{r.split}</td>
                      {allMetrics.map((m) => (
                        <td key={m} className="px-4 py-2 text-gray-600">
                          {r.metrics[m] !== undefined ? r.metrics[m].toFixed(4) : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Feature importances */}
            {importances && Object.keys(importances).length > 0 && (
              <div className="px-4 py-3 border-t border-gray-100">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">Feature importances</p>
                <div className="space-y-2">
                  {Object.entries(importances)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 15)
                    .map(([feat, imp]) => (
                      <div key={feat} className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 w-40 truncate flex-shrink-0">{feat}</span>
                        <div className="flex-1 bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-indigo-500 h-2 rounded-full"
                            style={{ width: `${Math.min(imp * 100, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400 w-12 text-right">{imp.toFixed(4)}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRun = async () => {
    try {
      const r = await runsApi.get(id);
      setRun(r);
      if (r.status === "completed" || r.status === "failed") {
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load run");
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  };

  useEffect(() => {
    fetchRun().finally(() => setLoading(false));

    intervalRef.current = setInterval(() => {
      fetchRun();
    }, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [id]);

  const duration =
    run?.started_at && run?.completed_at
      ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)
      : null;

  const summaryMetrics = run?.metrics as Record<string, unknown> | null;

  return (
    <AuthGuard>
      <div className="max-w-3xl">
        {run?.plan_id && (
          <Link href={`/plans/${run.plan_id}`} className="text-sm text-indigo-600 hover:underline mb-4 block">
            ← View plan
          </Link>
        )}

        <h1 className="text-2xl font-bold mb-6">Run</h1>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : run ? (
          <div className="space-y-6">
            {/* Status card */}
            <div className="bg-white rounded-lg border border-gray-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <StatusIcon status={run.status} />
                <span className="font-semibold capitalize">{run.status}</span>
                {(run.status === "queued" || run.status === "running") && (
                  <span className="text-sm text-gray-400 ml-1">Polling every 3s…</span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
                {run.started_at && (
                  <div>
                    <span className="text-gray-400 text-xs">Started</span>
                    <p>{new Date(run.started_at).toLocaleString()}</p>
                  </div>
                )}
                {run.completed_at && (
                  <div>
                    <span className="text-gray-400 text-xs">Completed</span>
                    <p>{new Date(run.completed_at).toLocaleString()}</p>
                  </div>
                )}
                {duration !== null && (
                  <div>
                    <span className="text-gray-400 text-xs">Duration</span>
                    <p>{duration}s</p>
                  </div>
                )}
              </div>

              {run.status === "failed" && run.error_message && (
                <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm font-mono">
                  {run.error_message}
                </div>
              )}
            </div>

            {/* Summary */}
            {run.status === "completed" && summaryMetrics && (
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5">
                <p className="text-xs font-medium text-indigo-600 uppercase tracking-wider mb-3">Best result</p>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-xs text-indigo-500 mb-1">Best model</p>
                    <p className="font-semibold text-indigo-900 text-sm">{String(summaryMetrics.best_model ?? "—")}</p>
                  </div>
                  <div>
                    <p className="text-xs text-indigo-500 mb-1">Metric</p>
                    <p className="font-semibold text-indigo-900 text-sm">{String(summaryMetrics.metric ?? "—")}</p>
                  </div>
                  <div>
                    <p className="text-xs text-indigo-500 mb-1">Score</p>
                    <p className="font-semibold text-indigo-900 text-sm">
                      {typeof summaryMetrics.best_score === "number"
                        ? summaryMetrics.best_score.toFixed(4)
                        : "—"}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Per-model results */}
            {run.status === "completed" && run.experiment_results.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-4">Model results</h2>
                <MetricsTable results={run.experiment_results} />
              </div>
            )}
          </div>
        ) : null}
      </div>
    </AuthGuard>
  );
}
