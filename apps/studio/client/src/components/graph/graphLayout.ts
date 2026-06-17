// Pure, dependency-free layered layout for the run graph.
//
// The engine is linear today, so the common case is a single column, but the
// layout groups nodes into layers by topological index so it is ready for DAGs.
// Executed nodes carry their graph index as `seq`; skipped nodes are appended by
// the backend with `seq = 1000 + topo_index`, so a unified topo index recovers
// the true graph order for both full runs and downstream-fork replays.

import type { GraphEdge, GraphNode } from "@/lib/api";

export const NODE_W = 210;
export const NODE_H = 70;
const X_GAP = 44;
const Y_GAP = 52;
const PAD = 24;

export interface PositionedNode {
  node: GraphNode;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PositionedEdge extends GraphEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface GraphLayout {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  width: number;
  height: number;
}

function topoIndex(n: GraphNode): number {
  return n.seq >= 1000 ? n.seq - 1000 : n.seq;
}

export function layoutGraph(nodes: GraphNode[], edges: GraphEdge[]): GraphLayout {
  const layers = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    const k = topoIndex(n);
    const arr = layers.get(k);
    if (arr) arr.push(n);
    else layers.set(k, [n]);
  }
  const layerKeys = Array.from(layers.keys()).sort((a, b) => a - b);

  const pos = new Map<string, PositionedNode>();
  let maxCols = 1;
  layerKeys.forEach((k, row) => {
    const group = layers.get(k)!;
    maxCols = Math.max(maxCols, group.length);
    group.forEach((n, col) => {
      pos.set(n.id, {
        node: n,
        x: PAD + col * (NODE_W + X_GAP),
        y: PAD + row * (NODE_H + Y_GAP),
        w: NODE_W,
        h: NODE_H,
      });
    });
  });

  const pedges: PositionedEdge[] = [];
  for (const e of edges) {
    const a = pos.get(e.from);
    const b = pos.get(e.to);
    if (!a || !b) continue;
    pedges.push({
      ...e,
      x1: a.x + a.w / 2,
      y1: a.y + a.h,
      x2: b.x + b.w / 2,
      y2: b.y,
    });
  }

  const rows = layerKeys.length;
  return {
    nodes: Array.from(pos.values()),
    edges: pedges,
    width: PAD * 2 + maxCols * NODE_W + (maxCols - 1) * X_GAP,
    height: PAD * 2 + rows * NODE_H + Math.max(0, rows - 1) * Y_GAP,
  };
}
