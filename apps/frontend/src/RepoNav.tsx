import { Link } from "react-router-dom";

export function RepoNav({ repositoryId }: { repositoryId: string }) {
  return (
    <nav>
      <Link to="/">Repositories</Link>
      <Link to={`/repos/${repositoryId}`}>Overview</Link>
      <Link to={`/repos/${repositoryId}/architecture`}>Architecture</Link>
      <Link to={`/repos/${repositoryId}/jobs`}>Jobs</Link>
    </nav>
  );
}
