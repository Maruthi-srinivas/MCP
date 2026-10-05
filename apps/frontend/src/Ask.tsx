import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { asError, request, startInvestigation, type PromptSpec } from "./api";

/** Prompt buttons and a question box. A prompt still starts the agent loop. */
export function Ask({ repositoryId }: { repositoryId: string }) {
  const navigate = useNavigate();
  const [prompts, setPrompts] = useState<PromptSpec[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    request<{ prompts: PromptSpec[] }>("/prompts")
      .then((body) => setPrompts(body.prompts))
      .catch((caught) => setError(asError(caught).message));
  }, []);

  async function start(input: { question?: string; prompt?: string; arguments?: Record<string, string> }) {
    setPending(true);
    setError("");
    try {
      const created = await startInvestigation(repositoryId, input);
      navigate(`/repos/${repositoryId}/chat/${created.session_id}`);
    } catch (caught) {
      const failure = asError(caught);
      setError(`${failure.code}: ${failure.message}`);
      setPending(false);
    }
  }

  return (
    <section className="ask">
      <h2>Ask</h2>
      {error ? <p className="error">{error}</p> : null}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (question.trim()) {
            void start({ question: question.trim() });
          }
        }}
      >
        <label>
          Question
          <input value={question} onChange={(event) => setQuestion(event.target.value)} />
        </label>
        <button type="submit" disabled={pending || !question.trim()}>
          Ask
        </button>
      </form>
      {prompts.map((prompt) => {
        const fields = prompt.arguments.filter((item) => item.name && item.name !== "repository_id");
        const missing = fields.some((field) => field.required && !(values[`${prompt.name}:${field.name}`] || "").trim());
        return (
          <form
            key={prompt.name}
            onSubmit={(event) => {
              event.preventDefault();
              const args: Record<string, string> = {};
              for (const field of fields) {
                args[field.name] = (values[`${prompt.name}:${field.name}`] || "").trim();
              }
              void start({ prompt: prompt.name, arguments: args });
            }}
          >
            <button type="submit" disabled={pending || missing}>
              {prompt.name}
            </button>
            {fields.map((field) => (
              <label key={field.name}>
                {field.name}
                <input
                  value={values[`${prompt.name}:${field.name}`] || ""}
                  onChange={(event) =>
                    setValues({ ...values, [`${prompt.name}:${field.name}`]: event.target.value })
                  }
                />
              </label>
            ))}
          </form>
        );
      })}
    </section>
  );
}
