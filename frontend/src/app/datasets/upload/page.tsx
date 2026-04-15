"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import AuthGuard from "@/components/layout/AuthGuard";
import { datasets as datasetsApi } from "@/lib/api";

export default function UploadPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectId = searchParams.get("project_id") ?? "";

  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !projectId) return;
    setError(null);
    setLoading(true);
    try {
      await datasetsApi.upload(projectId, name.trim(), goal.trim(), file);
      router.push(`/datasets?project_id=${projectId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="max-w-lg">
        <Link
          href={projectId ? `/datasets?project_id=${projectId}` : "/"}
          className="text-sm text-indigo-600 hover:underline mb-4 block"
        >
          ← Back to datasets
        </Link>
        <h1 className="text-2xl font-bold mb-6">Upload Dataset</h1>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Dataset name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. customer_churn"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Prediction goal</label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. Predict whether a customer will churn in the next 30 days"
              rows={3}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              required
            />
            <p className="text-xs text-gray-400 mt-1">
              Describe what you want to predict. This guides the AI plan generation.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">CSV file</label>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading || !file}
            className="w-full bg-indigo-600 text-white py-2 rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Uploading..." : "Upload dataset"}
          </button>
        </form>
      </div>
    </AuthGuard>
  );
}
