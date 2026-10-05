import { useEffect, type ReactElement } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { clearToken, hasToken, setUnauthorizedHandler } from "./api";
import { Architecture } from "./screens/Architecture";
import { Chat } from "./screens/Chat";
import { FileView } from "./screens/FileView";
import { Home } from "./screens/Home";
import { Jobs } from "./screens/Jobs";
import { Login } from "./screens/Login";
import { Overview } from "./screens/Overview";

function Guard({ children }: { children: ReactElement }) {
  if (!hasToken()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function App() {
  const navigate = useNavigate();
  useEffect(() => {
    setUnauthorizedHandler((code) => {
      clearToken();
      navigate("/login", { replace: true, state: { code } });
    });
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Guard><Home /></Guard>} />
      <Route path="/repos/:repositoryId" element={<Guard><Overview /></Guard>} />
      <Route path="/repos/:repositoryId/chat/:sessionId" element={<Guard><Chat /></Guard>} />
      <Route path="/repos/:repositoryId/architecture" element={<Guard><Architecture /></Guard>} />
      <Route path="/repos/:repositoryId/file" element={<Guard><FileView /></Guard>} />
      <Route path="/repos/:repositoryId/jobs" element={<Guard><Jobs /></Guard>} />
    </Routes>
  );
}
