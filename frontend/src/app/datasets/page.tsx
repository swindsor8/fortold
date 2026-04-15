"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import AuthGuard from "@/components/layout/AuthGuard";
import { datasets as datasetsApi, plans as plansApi, DatasetVersionResponse } from "@/lib/api";

export default function DatasetsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectId = searchParams.get("project_id") ?? "";

  const [versions, setVersions] = useState<DatasetVersionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    datasetsApi
      .list(projectId)
      .then(setVersions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleGeneratePlan = async (versionId: string) => {
    setGeneratingId(versionId);
    setError(null);
    try {
      const plan = await plansApi.generate(versionId);
      router.push(`/plans/${plan.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
      setGeneratingId(null);
    }
  };

  return (
    <AuthGuard>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link href="/" className="text-sm text-indigo-600 hover:underline mb-1 block">
            ← Projects
          </Link>
          <h1 className="text-2xl font-bold">Datasets</h1>
        </div>
        {projectId && (
          <Link
            href={`/datasets/upload?project_id=${projectId}`}
            className="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            Upload Dataset
          </Link>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm mb-4">
          {error}
        </div>
      )}

      {!projectId ? (
        <div className="text-center py-16 text-gray-500">
          <p>Select a project from the <Link href="/" className="text-indigo-600 hover:underline">dashboard</Link>.</p>
        </div>
      ) : loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : versions.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg font-medium mb-2">No datasets yet</p>
          <p className="text-sm">Upload a CSV file to get started.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Version</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Goal</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rows</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Uploaded</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {versions.map((v) => (
                <tr key={v.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{v.id.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-sm text-gray-600">v{v.version_number}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">{v.goal}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{v.row_count?.toLocaleString() ?? "—"}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {new Date(v.uploaded_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleGeneratePlan(v.id)}
                      disabled={generatingId === v.id}
                      className="bg-indigo-600 text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                    >
                      {generatingId === v.id ? "Generating…" : "Generate Plan"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AuthGuard>
  );
}
