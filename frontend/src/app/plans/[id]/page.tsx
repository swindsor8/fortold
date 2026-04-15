"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import AuthGuard from "@/components/layout/AuthGuard";
import { plans as plansApi, runs as runsApi, PlanResponse } from "@/lib/api";

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

const confidenceColors: Record<string, string> = {
  low: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-green-100 text-green-700",
};

function Badge({ label, colorClass }: { label: string; colorClass: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {label}
    </span>
  );
}

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchPlan = () => {
    plansApi
      .get(id)
      .then(setPlan)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchPlan();
  }, [id]);

  const handleReview = async (action: "approve" | "reject") => {
    setActionLoading(true);
    try {
      const updated = await plansApi.review(id, action);
      setPlan(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartRun = async () => {
    if (!plan) return;
    setActionLoading(true);
    try {
      const run = await runsApi.create(plan.id);
      router.push(`/runs/${run.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start run");
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      </AuthGuard>
    );
  }

  if (error || !plan) {
    return (
      <AuthGuard>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          {error ?? "Plan not found"}
        </div>
      </AuthGuard>
    );
  }

  const pj = plan.plan_json as Record<string, unknown>;
  const modelChoices = (pj.model_choices as Array<{ name: string; library: string; hyperparameters: Record<string, unknown> }>) ?? [];
  const risks = (pj.risks as string[]) ?? [];
  const featureCols = (pj.feature_columns as string[]) ?? [];
  const metrics = (pj.metrics as string[]) ?? [];
  const preprocessing = (pj.preprocessing as Record<string, unknown>) ?? {};

  return (
    <AuthGuard>
      <div className="max-w-3xl">
        <Link href="/" className="text-sm text-indigo-600 hover:underline mb-4 block">
          ← Projects
        </Link>

        <div className="flex items-center gap-3 mb-6">
          <h1 className="text-2xl font-bold">ML Plan</h1>
          <Badge label={plan.status} colorClass={statusColors[plan.status] ?? statusColors.draft} />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm mb-4">
            {error}
          </div>
        )}

        <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
          {/* Task overview */}
          <div className="p-5 grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Task type</p>
              <Badge
                label={String(pj.task_type ?? "")}
                colorClass="bg-indigo-100 text-indigo-700"
              />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Confidence</p>
              <Badge
                label={String(pj.confidence_level ?? "")}
                colorClass={confidenceColors[String(pj.confidence_level)] ?? confidenceColors.low}
              />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Target column</p>
              <code className="text-sm bg-gray-100 px-2 py-0.5 rounded">{String(pj.target_column ?? "")}</code>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Validation</p>
              <p className="text-sm text-gray-800">{String(pj.validation_method ?? "")}</p>
            </div>
          </div>

          {/* Rationale */}
          <div className="p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Rationale</p>
            <p className="text-sm text-gray-700 italic">{String(pj.rationale ?? "")}</p>
          </div>

          {/* Features */}
          <div className="p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
              Feature columns ({featureCols.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {featureCols.map((col) => (
                <code key={col} className="text-xs bg-gray-100 px-2 py-0.5 rounded">{col}</code>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">Strategy: {String(pj.feature_selection_strategy ?? "")}</p>
          </div>

          {/* Models */}
          <div className="p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">Models to train</p>
            <div className="space-y-3">
              {modelChoices.map((m, i) => (
                <div key={i} className="border border-gray-100 rounded-md p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-medium text-sm">{m.name}</span>
                    <Badge label={m.library} colorClass="bg-purple-100 text-purple-700" />
                  </div>
                  {Object.keys(m.hyperparameters).length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(m.hyperparameters).map(([k, v]) => (
                        <span key={k} className="text-xs bg-gray-50 border border-gray-200 px-2 py-0.5 rounded">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Metrics + Preprocessing */}
          <div className="p-5 grid grid-cols-2 gap-6">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Metrics</p>
              <div className="flex flex-wrap gap-1.5">
                {metrics.map((m) => (
                  <Badge key={m} label={m} colorClass="bg-blue-100 text-blue-700" />
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Preprocessing</p>
              <div className="space-y-1 text-sm text-gray-700">
                <p>Imputation: <span className="font-medium">{String(preprocessing.imputation ?? "")}</span></p>
                <p>Scaling: <span className="font-medium">{String(preprocessing.scaling ?? "")}</span></p>
                <p>Encode categoricals: <span className="font-medium">{String(preprocessing.encode_categoricals ?? "")}</span></p>
              </div>
            </div>
          </div>

          {/* Risks */}
          {risks.length > 0 && (
            <div className="p-5 bg-amber-50">
              <p className="text-xs font-medium text-amber-700 uppercase tracking-wider mb-2">Risks & caveats</p>
              <ul className="space-y-1">
                {risks.map((risk, i) => (
                  <li key={i} className="text-sm text-amber-800 flex gap-2">
                    <span className="mt-0.5">⚠</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Token usage */}
          <div className="px-5 py-3 bg-gray-50 text-xs text-gray-400">
            Model: {plan.llm_model} · {plan.prompt_tokens ?? "—"} prompt tokens · {plan.completion_tokens ?? "—"} completion tokens
          </div>
        </div>

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          {plan.status === "draft" && (
            <>
              <button
                onClick={() => handleReview("approve")}
                disabled={actionLoading}
                className="bg-green-600 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {actionLoading ? "..." : "Approve plan"}
              </button>
              <button
                onClick={() => handleReview("reject")}
                disabled={actionLoading}
                className="bg-red-100 text-red-700 px-5 py-2 rounded-md text-sm font-medium hover:bg-red-200 disabled:opacity-50 transition-colors"
              >
                {actionLoading ? "..." : "Reject"}
              </button>
            </>
          )}

          {plan.status === "approved" && (
            <button
              onClick={handleStartRun}
              disabled={actionLoading}
              className="bg-indigo-600 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {actionLoading ? "Starting..." : "Start run"}
            </button>
          )}
        </div>
      </div>
    </AuthGuard>
  );
}
