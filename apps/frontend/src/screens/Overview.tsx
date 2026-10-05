import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { asError, request, type Overview as OverviewBody } from "../api";
import { Ask } from "../Ask";
import { RepoNav } from "../RepoNav";
import "./Overview.css";

export function Overview() {
  const { repositoryId = "" } = useParams();
  const [body, setBody] = useState<OverviewBody | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    request<OverviewBody>(`/repositories/${repositoryId}/overview`)
      .then(setBody)
      .catch((caught) => setError(asError(caught).message));
  }, [repositoryId]);

  return (
    <main>
      <RepoNav repositoryId={repositoryId} />
      {error ? <p className="error">{error}</p> : null}
      {!body && !error ? <p className="loading">Loading overview…</p> : null}
      {body ? (
        <div className="regions">
          <section className="region">
            <h1>
              {body.owner}/{body.name}
            </h1>
            <p>{body.url}</p>
            <p>Ref: {body.ref || "default"}</p>
            <p>Commit: {body.resolved_commit}</p>
            <p>Status: {body.status}</p>
          </section>
          <section className="region">
            <h2>Languages</h2>
            {body.languages.length === 0 ? <p>No languages recorded.</p> : <p>{body.languages.join(", ")}</p>}
            <h2>Dependencies</h2>
            {body.dependencies.length === 0 ? <p>No dependencies recorded.</p> : null}
            <ul>
              {body.dependencies.map((item) => (
                <li key={`${item.name}:${item.source}`}>
                  {item.name} {item.version}
                </li>
              ))}
            </ul>
          </section>
          <section className="region">
            <h2>Frameworks</h2>
            {body.analysis_status !== "ready" ? <p>Analysis has not finished.</p> : null}
            {body.frameworks.length === 0 ? <p>No frameworks recorded.</p> : <p>{body.frameworks.join(", ")}</p>}
            <h2>Services</h2>
            {body.services.length === 0 ? <p>No services recorded.</p> : <p>{body.services.join(", ")}</p>}
            {body.analyzer_version ? <p>Analyzer {body.analyzer_version}</p> : null}
          </section>
        </div>
      ) : null}
      <Ask repositoryId={repositoryId} />
    </main>
  );
}
