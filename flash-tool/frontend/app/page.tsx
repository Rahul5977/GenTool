"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, type JobSummary } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const IN_PROGRESS = new Set(["analysing", "prompting", "imaging", "awaiting_approval", "generating", "stitching"]);

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function JobCard({ job }: { job: JobSummary }) {
  const active = IN_PROGRESS.has(job.status);
  const href =
    job.status === "done"
      ? `/jobs/${job.job_id}/result`
      : job.status === "awaiting_approval"
      ? `/jobs/${job.job_id}/review`
      : `/jobs/${job.job_id}/progress`;

  return (
    <div
      className={`relative p-5 rounded-xl border transition-all duration-200 hover:border-[#3a3a3a] ${
        active ? "border-[#1a5c3a]/60 bg-[#0d1a12]" : "border-[#2a2a2a] bg-[#161616]"
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={job.status} />
            <span className="text-xs text-[#4b5563] mono">{job.job_id.slice(0, 8)}</span>
          </div>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-sm font-semibold text-white">{job.coach}</span>
            <span className="text-xs text-[#4b5563]">·</span>
            <span className="text-xs text-[#6b7280]">{job.num_clips} clips</span>
            <span className="text-xs text-[#4b5563]">·</span>
            <span className="text-xs text-[#4b5563]">{timeAgo(job.created_at)}</span>
          </div>
        </div>
        <Link
          href={href}
          className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium border border-[#2a2a2a] text-[#9ca3af] hover:border-green-500/40 hover:text-green-400 transition-all"
        >
          {job.status === "done" ? "Watch" : job.status === "awaiting_approval" ? "Review" : "View"} →
        </Link>
      </div>

      {active && (
        <div className="mt-2">
          <div className="flex justify-between mb-1">
            <span className="text-xs text-[#4b5563]">Progress</span>
            <span className="text-xs text-green-400 mono">{job.progress}%</span>
          </div>
          <div className="h-1 rounded-full bg-[#1a1a1a] overflow-hidden">
            <div
              className="h-full rounded-full bg-green-500 transition-all duration-1000"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {job.status === "failed" && job.error && (
        <p className="mt-2 text-xs text-red-400 mono truncate" title={job.error}>
          ✗ {job.error}
        </p>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchJobs = useCallback(async () => {
    try {
      const data = await api.listJobs();
      setJobs(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  useEffect(() => {
    const hasActive = jobs.some((j) => IN_PROGRESS.has(j.status));
    if (!hasActive) return;
    const id = setInterval(fetchJobs, 5000);
    return () => clearInterval(id);
  }, [jobs, fetchJobs]);

  return (
    <main className="min-h-screen px-6 py-10 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-8 h-8 rounded-lg bg-[#1a5c3a] flex items-center justify-center text-green-300 text-sm font-bold">F</div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Flash Tool <span className="text-green-400">v2</span>
            </h1>
          </div>
          <p className="text-[#4b5563] text-sm pl-11">Script → Seamless Ad · SuperLiving</p>
        </div>
        <Link
          href="/new"
          className="px-5 py-2.5 rounded-xl bg-[#1a5c3a] text-white font-semibold text-sm hover:bg-[#22703f] transition-colors border border-green-500/20 shadow-[0_0_24px_rgba(26,92,58,0.4)]"
        >
          + New Ad
        </Link>
      </div>

      <div className="border-b border-[#1e1e1e] mb-8" />

      {/* Stats row */}
      {!loading && jobs.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: "Total", value: jobs.length },
            { label: "In Progress", value: jobs.filter((j) => IN_PROGRESS.has(j.status)).length },
            { label: "Completed", value: jobs.filter((j) => j.status === "done").length },
          ].map((s) => (
            <div key={s.label} className="bg-[#161616] border border-[#2a2a2a] rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-white mono">{s.value}</div>
              <div className="text-xs text-[#4b5563] mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Job list */}
      {loading ? (
        <div className="flex flex-col gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-28 rounded-xl shimmer" />
          ))}
        </div>
      ) : error ? (
        <div className="text-center py-20">
          <p className="text-red-400 text-sm mb-4">{error}</p>
          <button onClick={fetchJobs} className="text-xs text-[#6b7280] hover:text-white underline underline-offset-2">
            Retry
          </button>
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-24 border border-dashed border-[#2a2a2a] rounded-2xl">
          <p className="text-4xl mb-4">🎬</p>
          <p className="text-[#6b7280] text-sm">No ads generated yet.</p>
          <Link href="/new" className="inline-block mt-4 text-green-400 text-sm hover:text-green-300 underline underline-offset-2">
            Create your first ad →
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {jobs.map((job) => (
            <JobCard key={job.job_id} job={job} />
          ))}
        </div>
      )}
    </main>
  );
}
