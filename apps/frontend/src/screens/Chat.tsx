import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  asError,
  request,
  sendMessage,
  waitForInvestigation,
  type Investigation,
  type TraceRow,
} from "../api";
import { RepoNav } from "../RepoNav";
import "./Chat.css";

type Proposal = {
  proposal_id: string;
  status: string;
  diff: string;
  files: string[];
};

export function Chat() {
  const { repositoryId = "", sessionId = "" } = useParams();
  const [session, setSession] = useState<Investigation | null>(null);
  const [trace, setTrace] = useState<TraceRow[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setPending(true);
    waitForInvestigation(sessionId)
      .then(async (body) => {
        if (cancelled) {
          return;
        }
        setSession(body);
        if (body.job?.status === "failed") {
          setError(`${body.job.error_code || "INTERNAL_ERROR"}: The investigation failed.`);
        }
        const listed = await request<{ trace: TraceRow[] }>(`/investigations/${sessionId}/trace`);
        const proposed = await request<{ proposals: Proposal[] }>(`/investigations/${sessionId}/proposals`);
        if (!cancelled) {
          setTrace(listed.trace);
          setProposals(proposed.proposals);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(`${asError(caught).code}: ${asError(caught).message}`);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPending(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }
    setPending(true);
    setError("");
    try {
      await sendMessage(sessionId, { question: question.trim() });
      setQuestion("");
      const body = await waitForInvestigation(sessionId);
      setSession(body);
      const listed = await request<{ trace: TraceRow[] }>(`/investigations/${sessionId}/trace`);
      const proposed = await request<{ proposals: Proposal[] }>(`/investigations/${sessionId}/proposals`);
      setTrace(listed.trace);
      setProposals(proposed.proposals);
      if (body.job?.status === "failed") {
        setError(`${body.job.error_code || "INTERNAL_ERROR"}: The investigation failed.`);
      }
    } catch (caught) {
      const failure = asError(caught);
      setError(`${failure.code}: ${failure.message}`);
    } finally {
      setPending(false);
    }
  }

  async function decide(proposalId: string, action: "approve" | "reject" | "apply") {
    setError("");
    try {
      await request(`/investigations/${sessionId}/proposals/${proposalId}/${action}`, {
        method: "POST",
        body: "{}",
      });
      const proposed = await request<{ proposals: Proposal[] }>(`/investigations/${sessionId}/proposals`);
      setProposals(proposed.proposals);
    } catch (caught) {
      const failure = asError(caught);
      setError(`${failure.code}: ${failure.message}`);
    }
  }

  return (
    <main>
      <RepoNav repositoryId={repositoryId} />
      <h1>Investigation</h1>
      {pending ? <p className="loading">Waiting for the answer…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {(session?.messages || []).map((message, index) => (
        <article key={index} className={message.role === "assistant" ? "interpretation" : "user-message"}>
          <p>{message.text}</p>
          {(message.evidence || []).map((item) => (
            <p key={`${item.file}:${item.start_line}`} className="evidence">
              <Link to={`/repos/${repositoryId}/file?path=${encodeURIComponent(item.file)}&line=${item.start_line}`}>
                Found in {item.file}:{item.start_line}
              </Link>
              <span>
                {" "}
                via {item.mcp_server} {item.tool}
              </span>
            </p>
          ))}
        </article>
      ))}
      {proposals.map((proposal) => (
        <section key={proposal.proposal_id} className="proposal">
          <h2>Proposed change</h2>
          <p>{proposal.files.join(", ")}</p>
          <pre className="diff">{proposal.diff}</pre>
          <button type="button" disabled={proposal.status !== "proposed"} onClick={() => void decide(proposal.proposal_id, "approve")}>
            Approve
          </button>
          <button type="button" disabled={proposal.status !== "proposed"} onClick={() => void decide(proposal.proposal_id, "reject")}>
            Reject
          </button>
          <button type="button" disabled={proposal.status !== "approved"} onClick={() => void decide(proposal.proposal_id, "apply")}>
            Apply
          </button>
          {proposal.status === "applied" && proposal.files[0] ? (
            <p>
              <Link to={`/repos/${repositoryId}/file?path=${encodeURIComponent(proposal.files[0])}&line=1`}>
                {proposal.files[0]}
              </Link>
            </p>
          ) : null}
        </section>
      ))}
      <form onSubmit={onSubmit}>
        <label>
          Follow-up question
          <input value={question} onChange={(event) => setQuestion(event.target.value)} />
        </label>
        <button type="submit" disabled={pending || !question.trim()}>
          Send
        </button>
      </form>
      <h2>Trace</h2>
      {trace.length === 0 ? <p>No tool calls yet.</p> : null}
      <table>
        <tbody>
          {trace.map((row, index) => (
            <tr data-trace-row key={`${row.tool}:${index}`}>
              <td>{row.server}</td>
              <td>{row.tool}</td>
              <td>{row.status}</td>
              <td>{row.duration_ms} ms</td>
              <td>{Object.entries(row.arguments).map(([key, value]) => `${key}=${value}`).join(" ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
