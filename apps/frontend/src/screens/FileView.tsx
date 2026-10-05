import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { asError, request, type FileWindow } from "../api";
import { RepoNav } from "../RepoNav";
import "./FileView.css";

export function FileView() {
  const { repositoryId = "" } = useParams();
  const [params] = useSearchParams();
  const path = params.get("path") || "";
  const line = Number(params.get("line") || "1");
  const [file, setFile] = useState<FileWindow | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!path) {
      setError("INVALID_PATH: Path is required.");
      return;
    }
    setError("");
    setFile(null);
    request<FileWindow>(`/repositories/${repositoryId}/file?path=${encodeURIComponent(path)}&start_line=${line}`)
      .then(setFile)
      .catch((caught) => {
        const failure = asError(caught);
        setError(`${failure.code}: ${failure.message}`);
      });
  }, [repositoryId, path, line]);

  const lines = (file?.content || "").split("\n");

  return (
    <main>
      <RepoNav repositoryId={repositoryId} />
      <h1>{path || "File"}</h1>
      {error ? <p className="error">{error}</p> : null}
      {!file && !error ? <p className="loading">Loading file…</p> : null}
      {file ? (
        <ol className="file" start={file.start_line}>
          {lines.map((text, index) => {
            const number = file.start_line + index;
            return (
              <li key={number} className={number === line ? "file-line cited" : "file-line"}>
                {text || " "}
              </li>
            );
          })}
        </ol>
      ) : null}
      {file?.truncated ? <p>The window was truncated.</p> : null}
    </main>
  );
}
