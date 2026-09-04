"use client";

import { useState } from "react";
import Link from "next/link";
import {
  fetchWalletGraph,
  fetchTokenGraph,
  fetchClusterGraph,
  fetchShortestPath,
  fetchCreatorReputation,
  isValidWalletAddress,
  type WalletGraphRecord,
  type GraphNodeRecord,
  type GraphEdgeRecord,
  type ShortestPathRecord,
  type CreatorReputationRecord,
} from "../lib/read-api";

function shortId(val: string, visible = 8): string {
  if (!val || val.length <= visible * 2 + 1) return val || "";
  return `${val.slice(0, visible)}…${val.slice(-visible)}`;
}

export function WalletGraphExplorer() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchKind, setSearchKind] = useState<"wallet" | "token" | "cluster">("wallet");
  const [maxDepth, setMaxDepth] = useState(2);
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [graphData, setGraphData] = useState<WalletGraphRecord | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNodeRecord | null>(null);
  const [selectedReputation, setSelectedReputation] = useState<CreatorReputationRecord | null>(null);

  // Shortest Path state
  const [pathStart, setPathStart] = useState("");
  const [pathTarget, setPathTarget] = useState("");
  const [pathResult, setPathResult] = useState<ShortestPathRecord | null>(null);
  const [pathError, setPathError] = useState<string | null>(null);

  async function handleSearch(targetId?: string, kindOverride?: "wallet" | "token" | "cluster") {
    const idToSearch = targetId ?? searchQuery.trim();
    const kind = kindOverride ?? searchKind;
    if (!idToSearch) return;

    setLoading(true);
    setErrorMsg(null);
    setSelectedNode(null);
    setSelectedReputation(null);

    const filters = {
      maxDepth,
      maxNodes: 50,
      maxEdges: 100,
      outcomeFilter: outcomeFilter || undefined,
    };

    let res;
    if (kind === "token") {
      res = await fetchTokenGraph(idToSearch, filters);
    } else if (kind === "cluster") {
      res = await fetchClusterGraph(idToSearch, filters);
    } else {
      res = await fetchWalletGraph(idToSearch, filters);
    }

    setLoading(false);
    if (res.ok) {
      setGraphData(res.data);
      if (res.data.nodes.length > 0) {
        handleSelectNode(res.data.nodes[0]);
      }
    } else {
      setErrorMsg(`Graph query failed (${res.reason})`);
      setGraphData(null);
    }
  }

  async function handleSelectNode(node: GraphNodeRecord) {
    setSelectedNode(node);
    setSelectedReputation(null);
    const cleanAddr = node.id.replace(/^(wallet|token|cluster):/, "");
    if (node.kind === "WALLET" && isValidWalletAddress(cleanAddr)) {
      const repRes = await fetchCreatorReputation(cleanAddr);
      if (repRes.ok) {
        setSelectedReputation(repRes.data);
      }
    }
  }

  async function handleFindPath(e: React.FormEvent) {
    e.preventDefault();
    if (!pathStart.trim() || !pathTarget.trim()) return;
    setPathError(null);
    setPathResult(null);

    const res = await fetchShortestPath(pathStart.trim(), pathTarget.trim());
    if (res.ok) {
      setPathResult(res.data);
    } else {
      setPathError(`Path search failed (${res.reason})`);
    }
  }

  return (
    <div className="space-y-6">
      {/* Search & Controls */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">Search Graph Projection</h2>
        <div className="flex flex-wrap items-center gap-3">
          <select
            aria-label="Search Kind"
            value={searchKind}
            onChange={(e) => setSearchKind(e.target.value as "wallet" | "token" | "cluster")}
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2 focus:outline-none focus:border-blue-500"
          >
            <option value="wallet">Wallet Address</option>
            <option value="token">Token Mint</option>
            <option value="cluster">Actor Cluster ID</option>
          </select>

          <input
            type="text"
            placeholder="Enter address, mint, or cluster ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 min-w-[280px] bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2 font-mono focus:outline-none focus:border-blue-500"
          />

          <select
            aria-label="Max Depth"
            value={maxDepth}
            onChange={(e) => setMaxDepth(Number(e.target.value))}
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2"
          >
            <option value={1}>Depth: 1</option>
            <option value={2}>Depth: 2</option>
            <option value={3}>Depth: 3</option>
          </select>

          <select
            aria-label="Outcome Filter"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2"
          >
            <option value="">All Outcomes</option>
            <option value="STRONG_WINNER">STRONG_WINNER</option>
            <option value="WINNER">WINNER</option>
            <option value="MIXED">MIXED</option>
            <option value="FAILED">FAILED</option>
            <option value="SEVERE_DUMP">SEVERE_DUMP</option>
            <option value="RUG_OR_LIQUIDITY_COLLAPSE">RUG_OR_LIQUIDITY_COLLAPSE</option>
          </select>

          <button
            onClick={() => handleSearch()}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs px-4 py-2 rounded transition disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search Graph"}
          </button>
        </div>
        {errorMsg && <p className="text-xs text-rose-400 font-mono mt-2">{errorMsg}</p>}
      </div>

      {/* Main Explorer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Graph Display Area */}
        <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-md font-semibold text-slate-200">
              Graph Visualization {graphData && `(${graphData.nodes.length} nodes, ${graphData.edges.length} edges)`}
            </h3>
            {graphData?.hasMore && (
              <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                Bounded projection reached
              </span>
            )}
          </div>

          {!graphData ? (
            <div className="h-80 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-center p-6 text-center text-slate-400">
              <div>
                <p className="text-sm">Search a wallet, mint, or cluster above to explore relationships.</p>
                <p className="text-xs text-slate-500 mt-2">
                  Node links connect creators, funders, token launches, and side-wallets with explicit outcome evidence.
                </p>
              </div>
            </div>
          ) : graphData.nodes.length === 0 ? (
            <div className="h-80 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-center text-slate-400 text-sm">
              No matching nodes found for this query.
            </div>
          ) : (
            <div className="space-y-6">
              {/* Node List View / Visual Representation */}
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-4 max-h-[420px] overflow-y-auto">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graphData.nodes.map((node) => {
                    const isSelected = selectedNode?.id === node.id;
                    const outcome = String(node.properties?.outcome ?? "UNKNOWN");
                    let badgeColor = "bg-slate-800 text-slate-300 border-slate-700";
                    if (node.kind === "WALLET") badgeColor = "bg-blue-500/10 text-blue-400 border-blue-500/30";
                    if (node.kind === "TOKEN") {
                      if (["STRONG_WINNER", "WINNER"].includes(outcome)) {
                        badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
                      } else if (["RUG_OR_LIQUIDITY_COLLAPSE", "SEVERE_DUMP"].includes(outcome)) {
                        badgeColor = "bg-rose-500/10 text-rose-400 border-rose-500/30";
                      } else {
                        badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                      }
                    }

                    return (
                      <button
                        key={node.id}
                        onClick={() => handleSelectNode(node)}
                        className={`text-left p-3 rounded-lg border transition ${
                          isSelected
                            ? "bg-slate-800 border-blue-500 shadow-md ring-1 ring-blue-500"
                            : "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${badgeColor}`}>
                            {node.kind}
                          </span>
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              node.qualityState === "FRESH"
                                ? "bg-emerald-500/10 text-emerald-400"
                                : "bg-amber-500/10 text-amber-400"
                            }`}
                          >
                            {node.qualityState}
                          </span>
                        </div>
                        <p className="text-xs font-mono font-semibold text-slate-200 mt-2 truncate">
                          {node.label || shortId(node.id)}
                        </p>
                        {node.kind === "TOKEN" && (
                          <p className="text-[11px] text-slate-400 mt-1">Outcome: {outcome}</p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Edge Connections List */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Relationships ({graphData.edges.length})
                </h4>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2 max-h-48 overflow-y-auto">
                  {graphData.edges.length === 0 ? (
                    <p className="text-xs text-slate-500">No edges in current projection.</p>
                  ) : (
                    graphData.edges.map((edge) => (
                      <div
                        key={edge.id}
                        className="flex flex-wrap items-center justify-between gap-2 text-xs py-1.5 px-2 bg-slate-900/50 rounded border border-slate-800/60"
                      >
                        <span className="font-mono text-slate-300">{shortId(edge.fromId)}</span>
                        <span className="font-mono text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded text-[10px]">
                          &rarr; {edge.kind} &rarr;
                        </span>
                        <span className="font-mono text-slate-300">{shortId(edge.toId)}</span>
                        <span className="text-[10px] font-mono text-slate-500">
                          {edge.qualityState}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Side Panel: Node Inspection */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-6">
          <h3 className="text-md font-semibold text-slate-200">Node Inspection</h3>

          {!selectedNode ? (
            <p className="text-xs text-slate-400">Select a node in the graph visualization to view detailed evidence.</p>
          ) : (
            <div className="space-y-4 text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-medium">Node Kind:</span>
                  <span className="font-mono text-blue-400">{selectedNode.kind}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-medium">Quality State:</span>
                  <span
                    className={`font-mono ${
                      selectedNode.qualityState === "FRESH" ? "text-emerald-400" : "text-amber-400 font-bold"
                    }`}
                  >
                    {selectedNode.qualityState}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block mb-1">ID:</span>
                  <span className="font-mono text-slate-200 break-all bg-slate-900 p-1 rounded block">
                    {selectedNode.id}
                  </span>
                </div>
              </div>

              {/* Creator Reputation Panel */}
              {selectedReputation && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300 border-b border-slate-800 pb-1">
                    Creator Reputation
                  </h4>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Class:</span>
                    <span className="font-mono text-purple-400 font-semibold">
                      {selectedReputation.reputationClass}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Score:</span>
                    <span className="font-mono text-emerald-400 font-bold">
                      {selectedReputation.score} / 100
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 font-medium">Total Launches:</span>
                    <span className="font-mono text-slate-200">{selectedReputation.launchesTotal}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Win Rate:</span>
                    <span className="font-mono text-slate-200">
                      {Math.round(selectedReputation.winnerRate * 100)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Severe Failures / Rugs:</span>
                    <span className="font-mono text-rose-400">
                      {Math.round(selectedReputation.severeFailureRate * 100)}% /{" "}
                      {Math.round(selectedReputation.rugRate * 100)}%
                    </span>
                  </div>
                  {selectedReputation.reasonCodes.length > 0 && (
                    <div className="pt-1">
                      <span className="text-slate-400 block mb-1">Reason Codes:</span>
                      <div className="flex flex-wrap gap-1">
                        {selectedReputation.reasonCodes.map((code) => (
                          <span
                            key={code}
                            className="bg-slate-900 border border-slate-800 text-slate-300 text-[10px] font-mono px-1.5 py-0.5 rounded"
                          >
                            {code}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Node Properties */}
              {Object.keys(selectedNode.properties || {}).length > 0 && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                  <h4 className="text-xs font-semibold text-slate-300 border-b border-slate-800 pb-1">
                    Properties
                  </h4>
                  {Object.entries(selectedNode.properties).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-400">{k}:</span>
                      <span className="font-mono text-slate-200">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Action: Expand Neighbors */}
              <button
                onClick={() => {
                  const clean = selectedNode.id.replace(/^(wallet|token|cluster):/, "");
                  const kind = selectedNode.kind === "TOKEN" ? "token" : selectedNode.kind === "ACTOR_CLUSTER" ? "cluster" : "wallet";
                  handleSearch(clean, kind);
                }}
                className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium py-2 rounded text-xs transition border border-slate-700"
              >
                Expand Neighbors &rarr;
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Shortest Path Tool */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">Explainable Shortest Path</h2>
        <form onSubmit={handleFindPath} className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Start Node (e.g. wallet address or mint)..."
            value={pathStart}
            onChange={(e) => setPathStart(e.target.value)}
            className="flex-1 min-w-[240px] bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2 font-mono focus:outline-none focus:border-blue-500"
          />
          <span className="text-slate-500 font-mono text-xs">&rarr;</span>
          <input
            type="text"
            placeholder="Target Node (e.g. rug token mint)..."
            value={pathTarget}
            onChange={(e) => setPathTarget(e.target.value)}
            className="flex-1 min-w-[240px] bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2 font-mono focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-4 py-2 rounded transition"
          >
            Find Path
          </button>
        </form>

        {pathError && <p className="text-xs text-rose-400 font-mono">{pathError}</p>}

        {pathResult && (
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
            <h4 className="text-xs font-semibold text-slate-300">
              Path Hops ({pathResult.nodes.length - 1} hops)
            </h4>
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              {pathResult.nodes.map((nodeId, idx) => (
                <span key={nodeId} className="flex items-center gap-2">
                  <span className="bg-slate-900 border border-slate-800 text-blue-400 px-2 py-1 rounded">
                    {shortId(nodeId)}
                  </span>
                  {idx < pathResult.nodes.length - 1 && (
                    <span className="text-slate-500">&rarr;</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
