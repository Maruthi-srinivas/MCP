import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { asError, request, setToken } from "../api";
import "./Login.css";

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const returned = (location.state as { code?: string } | null)?.code || "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setToken(value);
    try {
      await request<{ caller_id: string }>("/me");
      navigate("/");
    } catch (caught) {
      setError(asError(caught).code);
    }
  }

  return (
    <main className="login">
      <h1>Sign in</h1>
      <p>Paste the local token. A refresh drops it.</p>
      {returned ? <p className="error">{returned}</p> : null}
      <form onSubmit={submit}>
        <label>
          Token
          <input value={value} onChange={(event) => setValue(event.target.value)} autoComplete="off" />
        </label>
        <button type="submit">Sign in</button>
      </form>
      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
