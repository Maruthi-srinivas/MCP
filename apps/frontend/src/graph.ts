/** Place stored nodes in rows and draw the edges. This does not edit the graph. */

import type { GraphEdge, GraphNode } from "./api";

export type PlacedNode = GraphNode & { x: number; y: number; width: number; height: number };
export type PlacedEdge = { x1: number; y1: number; x2: number; y2: number };

const COLUMN_WIDTH = 220;
const ROW_HEIGHT = 88;
const NODE_WIDTH = 180;
const NODE_HEIGHT = 48;

export function place(nodes: GraphNode[], edges: GraphEdge[]): {
  nodes: PlacedNode[];
  edges: PlacedEdge[];
  width: number;
  height: number;
} {
  const placed = nodes.map((node, index) => {
    const column = index % 3;
    const row = Math.floor(index / 3);
    return {
      ...node,
      x: 16 + column * COLUMN_WIDTH,
      y: 16 + row * ROW_HEIGHT,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    };
  });
  const lines: PlacedEdge[] = [];
  for (const edge of edges) {
    const from = findEnd(placed, edge.source, edge.path);
    const to = findEnd(placed, edge.target, edge.target_path);
    if (!from || !to || from.id === to.id) {
      continue;
    }
    lines.push({
      x1: from.x + from.width,
      y1: from.y + from.height / 2,
      x2: to.x,
      y2: to.y + to.height / 2,
    });
  }
  const width = Math.max(640, ...placed.map((node) => node.x + node.width + 24), 640);
  const height = Math.max(160, ...placed.map((node) => node.y + node.height + 24), 160);
  return { nodes: placed, edges: lines, width, height };
}

function findEnd(nodes: PlacedNode[], name: string, path: string | undefined): PlacedNode | undefined {
  return (
    nodes.find((node) => node.name === name && (!path || node.path === path)) ||
    nodes.find((node) => node.path === name) ||
    nodes.find((node) => path && node.path === path && node.kind === "file")
  );
}
