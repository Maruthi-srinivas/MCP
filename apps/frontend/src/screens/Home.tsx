import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { asError, importRepository, request, type RepositorySummary, waitUntilReady } from "../api";
import "./Home.css";

export function Home() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("");
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    request<{ repositories: RepositorySummary[] }>("/repositories")
      .then((body) => setRepositories(body.repositories))
      .catch((caught) => setError(asError(caught).message));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    setMessage("Importing…");
    try {
      const created = await importRepository(url.trim(), ref.trim());
      await waitUntilReady(created.repository_id, created.job_id);
      navigate(`/repos/${created.repository_id}`);
    } catch (caught) {
      const failure = asError(caught);
      setError(`${failure.code}: ${failure.message}`);
      setMessage("");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="home">
      <h1>Repository Investigator</h1>
      <form onSubmit={onSubmit}>
        <label>
          Repository URL
          <input value={url} onChange={(event) => setUrl(event.target.value)} required />
        </label>
        <label>
          Ref
          <input value={ref} onChange={(event) => setRef(event.target.value)} placeholder="optional branch or commit" />
        </label>
        <button type="submit" disabled={pending}>
          Import
        </button>
      </form>
      {message ? <p className="loading">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      <h2>Repositories</h2>
      {repositories.length === 0 ? <p>No repositories yet.</p> : null}
      <ul>
        {repositories.map((item) => (
          <li key={item.repository_id}>
            <Link to={`/repos/${item.repository_id}`}>
              {item.owner}/{item.name}
            </Link>
            <span>{item.status}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
