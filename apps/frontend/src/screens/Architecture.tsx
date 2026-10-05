import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { asError, request, type GraphEdge, type GraphNode } from "../api";
import { place, type PlacedNode } from "../graph";
import { RepoNav } from "../RepoNav";
import "./Architecture.css";

type ArchitectureBody = {
  status: string;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  architecture?: { nodes?: GraphNode[]; edges?: GraphEdge[] };
};

export function Architecture() {
  const { repositoryId = "" } = useParams();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [ready, setReady] = useState(false);
  const [selected, setSelected] = useState<PlacedNode | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    request<ArchitectureBody>(`/repositories/${repositoryId}/architecture`)
      .then((body) => {
        const graph = body.architecture || body;
        setReady(body.status === "ready");
        setNodes(graph.nodes || []);
        setEdges(graph.edges || []);
        setLoaded(true);
      })
      .catch((caught) => setError(asError(caught).message));
  }, [repositoryId]);

  const layout = place(nodes, edges);

  return (
    <main>
      <RepoNav repositoryId={repositoryId} />
      <h1>Architecture</h1>
      {error ? <p className="error">{error}</p> : null}
      {loaded && !ready && !error ? (
        <p>
          Analysis has not finished. <Link to={`/repos/${repositoryId}/jobs`}>Open jobs</Link>
        </p>
      ) : null}
      {ready && nodes.length === 0 ? <p>No nodes were stored.</p> : null}
      {ready && nodes.length > 0 ? (
        <div className="graph-wrap">
          <svg width={layout.width} height={layout.height} role="img" aria-label="Architecture graph">
            {layout.edges.map((edge, index) => (
              <line key={index} x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} />
            ))}
            {layout.nodes.map((node) => (
              <g key={node.id} onClick={() => setSelected(node)}>
                <rect x={node.x} y={node.y} width={node.width} height={node.height} rx={4} />
                <text x={node.x + 8} y={node.y + 28}>
                  {node.name}
                </text>
              </g>
            ))}
          </svg>
          {selected ? (
            <aside className="detail">
              <h2>{selected.name}</h2>
              <p>{selected.kind}</p>
              <p>
                <Link to={`/repos/${repositoryId}/file?path=${encodeURIComponent(selected.path)}&line=${selected.line}`}>
                  Found in {selected.path}:{selected.line}
                </Link>
              </p>
            </aside>
          ) : (
            <p>Select a node to see its file and line.</p>
          )}
        </div>
      ) : null}
    </main>
  );
}
