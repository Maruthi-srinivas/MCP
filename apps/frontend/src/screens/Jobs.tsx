import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { asError, request, type JobRow } from "../api";
import { RepoNav } from "../RepoNav";
import "./Jobs.css";

export function Jobs() {
  const { repositoryId = "" } = useParams();
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    const body = await request<{ jobs: JobRow[] }>(`/repositories/${repositoryId}/jobs`);
    setJobs(body.jobs);
  }

  useEffect(() => {
    load().catch((caught) => setError(asError(caught).message));
  }, [repositoryId]);

  async function rerun() {
    setPending(true);
    setError("");
    try {
      await request(`/repositories/${repositoryId}/analyze`, { method: "POST" });
      const deadline = Date.now() + 90000;
      while (Date.now() < deadline) {
        const body = await request<{ jobs: JobRow[] }>(`/repositories/${repositoryId}/jobs`);
        setJobs(body.jobs);
        const analyze = body.jobs.find((job) => job.kind === "analyze");
        if (analyze && (analyze.status === "succeeded" || analyze.status === "failed")) {
          if (analyze.status === "failed") {
            setError(`${analyze.error_code || "INTERNAL_ERROR"}: Analysis failed.`);
          }
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 400));
      }
      setError("TOOL_TIMEOUT: Analysis did not finish.");
    } catch (caught) {
      const failure = asError(caught);
      setError(`${failure.code}: ${failure.message}`);
    } finally {
      setPending(false);
    }
  }

  return (
    <main>
      <RepoNav repositoryId={repositoryId} />
      <h1>Jobs</h1>
      <button type="button" onClick={() => void rerun()} disabled={pending}>
        Run analysis
      </button>
      {pending ? <p className="loading">Running analysis…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {jobs.length === 0 ? <p>No jobs yet.</p> : null}
      <ul>
        {jobs.map((job) => (
          <li key={job.id}>
            <span>{job.kind}</span>
            <span>{job.status}</span>
            <span>{job.error_code || ""}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
