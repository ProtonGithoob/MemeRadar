"use client";

import { useState, useMemo } from "react";
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
  type GraphFilters,
} from "../lib/read-api";

function shortId(val: string, visible = 8): string {
  if (!val || val.length <= visible * 2 + 1) return val || "";
  return `${val.slice(0, visible)}…${val.slice(-visible)}`;
}

interface NodePosition {
  x: number;
  y: number;
}

export function WalletGraphExplorer() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchKind, setSearchKind] = useState<"wallet" | "token" | "cluster">("wallet");
  const [maxDepth, setMaxDepth] = useState(2);
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [venueFilter, setVenueFilter] = useState("");
  const [walletRoleFilter, setWalletRoleFilter] = useState("");
  const [qualityFilter, setQualityFilter] = useState("");
  const [dateFromFilter, setDateFromFilter] = useState("");
  const [dateToFilter, setDateToFilter] = useState("");
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

  // SVG Pan & Zoom state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  async function handleSearch(targetId?: string, kindOverride?: "wallet" | "token" | "cluster") {
    const idToSearch = targetId ?? searchQuery.trim();
    const kind = kindOverride ?? searchKind;
    if (!idToSearch) return;

    setLoading(true);
    setErrorMsg(null);
    setSelectedNode(null);
    setSelectedReputation(null);

    const filters: GraphFilters = {
      maxDepth,
      maxNodes: 50,
      maxEdges: 100,
      outcomeFilter: outcomeFilter || undefined,
      riskOutcomeClass: outcomeFilter || undefined,
      venue: venueFilter || undefined,
      walletRole: walletRoleFilter || undefined,
      evidenceQuality: qualityFilter || undefined,
      dateFrom: dateFromFilter || undefined,
      dateTo: dateToFilter || undefined,
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

  // Layout math: concentric circles around center (400, 240)
  const nodePositions = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) return new Map<string, NodePosition>();
    const posMap = new Map<string, NodePosition>();
    const width = 800;
    const height = 480;
    const centerX = width / 2;
    const centerY = height / 2;

    const rootId = graphData.nodes[0].id;
    posMap.set(rootId, { x: centerX, y: centerY });

    const remaining = graphData.nodes.slice(1);
    const n = remaining.length;
    if (n === 0) return posMap;

    // Distribute remaining nodes in 2 concentric rings
    const innerCount = Math.min(n, 12);
    const outerCount = Math.max(0, n - 12);

    const rInner = Math.min(width, height) * 0.28;
    const rOuter = Math.min(width, height) * 0.42;

    for (let i = 0; i < innerCount; i++) {
      const angle = (2 * Math.PI * i) / innerCount - Math.PI / 2;
      posMap.set(remaining[i].id, {
        x: centerX + rInner * Math.cos(angle),
        y: centerY + rInner * Math.sin(angle),
      });
    }

    for (let i = 0; i < outerCount; i++) {
      const angle = (2 * Math.PI * i) / outerCount - Math.PI / 4;
      posMap.set(remaining[innerCount + i].id, {
        x: centerX + rOuter * Math.cos(angle),
        y: centerY + rOuter * Math.sin(angle),
      });
    }

    return posMap;
  }, [graphData]);

  // Shortest path nodes & edges sets for glowing highlight
  const pathNodeSet = useMemo(() => new Set(pathResult?.nodes ?? []), [pathResult]);
  const pathEdgeSet = useMemo(() => {
    if (!pathResult?.edges) return new Set<string>();
    return new Set(pathResult.edges.map((e) => String(e.id ?? "")));
  }, [pathResult]);

  // Canvas Mouse Pan/Drag Handlers
  function handleMouseDown(e: React.MouseEvent) {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }

  function handleMouseUp() {
    setIsDragging(false);
  }

  return (
    <div className="space-y-6">
      {/* Search & Extended Filter Controls */}
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
            <option value={4}>Depth: 4</option>
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

          <select
            aria-label="Venue Filter"
            value={venueFilter}
            onChange={(e) => setVenueFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2"
          >
            <option value="">All Venues</option>
            <option value="raydium">Raydium</option>
            <option value="pumpfun">Pump.fun</option>
            <option value="orca">Orca</option>
            <option value="meteora">Meteora</option>
          </select>

          <select
            aria-label="Wallet Role"
            value={walletRoleFilter}
            onChange={(e) => setWalletRoleFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2"
          >
            <option value="">All Roles</option>
            <option value="WALLET">Wallet</option>
            <option value="CREATOR">Creator / Deployer</option>
            <option value="FUNDER">Funder</option>
            <option value="SNIPER">Sniper</option>
            <option value="SIDE_WALLET">Side Wallet</option>
          </select>

          <select
            aria-label="Evidence Quality"
            value={qualityFilter}
            onChange={(e) => setQualityFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded px-3 py-2"
          >
            <option value="">All Quality</option>
            <option value="FRESH">FRESH</option>
            <option value="STALE">STALE</option>
            <option value="UNKNOWN">UNKNOWN</option>
          </select>

          <button
            onClick={() => handleSearch()}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs px-4 py-2 rounded transition disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search Graph"}
          </button>
        </div>

        {/* Date Range Inputs */}
        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-slate-800/60 text-xs">
          <span className="text-slate-400 font-medium">Time Window:</span>
          <input
            type="datetime-local"
            aria-label="Date From"
            value={dateFromFilter}
            onChange={(e) => setDateFromFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded px-2 py-1"
          />
          <span className="text-slate-500">&rarr;</span>
          <input
            type="datetime-local"
            aria-label="Date To"
            value={dateToFilter}
            onChange={(e) => setDateToFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded px-2 py-1"
          />
        </div>

        {errorMsg && <p className="text-xs text-rose-400 font-mono mt-2">{errorMsg}</p>}
      </div>

      {/* Main Explorer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Node-Link Graph Display Canvas */}
        <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4 flex flex-col">
          <div className="flex items-center justify-between">
            <h3 className="text-md font-semibold text-slate-200">
              Interactive Node-Link Graph {graphData && `(${graphData.nodes.length} nodes, ${graphData.edges.length} edges)`}
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setZoom((z) => Math.min(z * 1.25, 3))}
                title="Zoom In"
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono px-2 py-1 rounded border border-slate-700"
              >
                +
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(z / 1.25, 0.4))}
                title="Zoom Out"
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono px-2 py-1 rounded border border-slate-700"
              >
                -
              </button>
              <button
                onClick={() => {
                  setZoom(1);
                  setPan({ x: 0, y: 0 });
                }}
                title="Reset View"
                className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-2.5 py-1 rounded border border-slate-700"
              >
                Fit / Reset
              </button>
              {graphData?.hasMore && (
                <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                  Bounded
                </span>
              )}
            </div>
          </div>

          {!graphData ? (
            <div className="h-96 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-center p-6 text-center text-slate-400">
              <div>
                <p className="text-sm">Search a wallet, mint, or cluster above to explore relationships.</p>
                <p className="text-xs text-slate-500 mt-2">
                  Interactive node links connect creators, funders, token launches, and side-wallets with explicit outcome evidence.
                </p>
              </div>
            </div>
          ) : graphData.nodes.length === 0 ? (
            <div className="h-96 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-center text-slate-400 text-sm">
              No matching nodes found for this query.
            </div>
          ) : (
            <div className="space-y-4">
              {/* SVG Node-Link Canvas */}
              <div
                className="w-full h-[480px] bg-slate-950 border border-slate-800 rounded-lg overflow-hidden relative cursor-grab active:cursor-grabbing select-none"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                <svg
                  width="100%"
                  height="100%"
                  viewBox="0 0 800 480"
                  className="w-full h-full"
                >
                  <defs>
                    <marker
                      id="arrow"
                      viewBox="0 0 10 10"
                      refX="22"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                    </marker>
                    <marker
                      id="arrow-path"
                      viewBox="0 0 10 10"
                      refX="22"
                      refY="5"
                      markerWidth="7"
                      markerHeight="7"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#eab308" />
                    </marker>
                  </defs>

                  <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                    {/* Directional Edges */}
                    {graphData.edges.map((edge) => {
                      const fromPos = nodePositions.get(edge.fromId);
                      const toPos = nodePositions.get(edge.toId);
                      if (!fromPos || !toPos) return null;

                      const isInPath = pathEdgeSet.has(edge.id);
                      let strokeColor = isInPath ? "#eab308" : "#475569";
                      if (!isInPath) {
                        if (edge.kind === "CREATED" || edge.kind === "DEPLOYED") strokeColor = "#38bdf8";
                        else if (edge.kind === "FUNDED") strokeColor = "#818cf8";
                        else if (edge.kind === "SNIPED" || edge.kind === "EARLY_BOUGHT") strokeColor = "#f43f5e";
                        else if (edge.kind === "TRANSFERRED_TO") strokeColor = "#fbbf24";
                      }

                      const isStale = edge.qualityState !== "FRESH";

                      return (
                        <g key={edge.id}>
                          <line
                            x1={fromPos.x}
                            y1={fromPos.y}
                            x2={toPos.x}
                            y2={toPos.y}
                            stroke={strokeColor}
                            strokeWidth={isInPath ? 3 : 1.5}
                            strokeDasharray={isStale ? "4,4" : undefined}
                            markerEnd={isInPath ? "url(#arrow-path)" : "url(#arrow)"}
                            opacity={0.8}
                          />
                          {/* Midpoint Label */}
                          <text
                            x={(fromPos.x + toPos.x) / 2}
                            y={(fromPos.y + toPos.y) / 2 - 4}
                            fill={isInPath ? "#fef08a" : "#94a3b8"}
                            fontSize="9"
                            fontFamily="monospace"
                            textAnchor="middle"
                            className="pointer-events-none"
                          >
                            {edge.kind}
                          </text>
                        </g>
                      );
                    })}

                    {/* Nodes */}
                    {graphData.nodes.map((node) => {
                      const pos = nodePositions.get(node.id);
                      if (!pos) return null;

                      const isSelected = selectedNode?.id === node.id;
                      const isInPath = pathNodeSet.has(node.id);

                      const outcome = String(node.properties?.outcome ?? "UNKNOWN");
                      let fillColor = "#3b82f6"; // WALLET default blue
                      let strokeColor = "#60a5fa";

                      if (node.kind === "TOKEN") {
                        if (["STRONG_WINNER", "WINNER"].includes(outcome)) {
                          fillColor = "#10b981"; // Emerald green
                          strokeColor = "#34d399";
                        } else if (["RUG_OR_LIQUIDITY_COLLAPSE", "SEVERE_DUMP"].includes(outcome)) {
                          fillColor = "#f43f5e"; // Rose red
                          strokeColor = "#fb7185";
                        } else {
                          fillColor = "#f59e0b"; // Amber orange
                          strokeColor = "#fbbf24";
                        }
                      } else if (node.kind === "ACTOR_CLUSTER" || node.kind === "POOL") {
                        fillColor = "#8b5cf6"; // Purple
                        strokeColor = "#a78bfa";
                      }

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${pos.x}, ${pos.y})`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectNode(node);
                          }}
                          className="cursor-pointer group"
                        >
                          {/* Selected / Shortest Path Ring Glow */}
                          {(isSelected || isInPath) && (
                            <circle
                              r="20"
                              fill="none"
                              stroke={isSelected ? "#3b82f6" : "#eab308"}
                              strokeWidth="3.5"
                              className="animate-pulse"
                            />
                          )}

                          {/* Node Circle */}
                          <circle
                            r="14"
                            fill={fillColor}
                            stroke={strokeColor}
                            strokeWidth="2"
                            className="transition-transform group-hover:scale-110"
                          />

                          {/* Node Label Text */}
                          <text
                            y="26"
                            fill="#f8fafc"
                            fontSize="10"
                            fontFamily="monospace"
                            fontWeight="600"
                            textAnchor="middle"
                            className="pointer-events-none drop-shadow"
                          >
                            {node.label || shortId(node.id, 5)}
                          </text>

                          {/* Kind Badge Text */}
                          <text
                            y="38"
                            fill="#94a3b8"
                            fontSize="8"
                            fontFamily="monospace"
                            textAnchor="middle"
                            className="pointer-events-none"
                          >
                            {node.kind}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </svg>
              </div>

              {/* Edge Connections List */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Relationships ({graphData.edges.length})
                </h4>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2 max-h-36 overflow-y-auto">
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

        {/* Side Panel: Node Inspection & Creator Reputation */}
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

              {/* Complete Creator Reputation Panel (all 20 audit fields) */}
              {selectedReputation && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300 border-b border-slate-800 pb-1 flex items-center justify-between">
                    <span>Creator Reputation</span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {selectedReputation.sufficientOutcomeSamples ? "Sufficient Samples" : "Unproven Sample Size"}
                    </span>
                  </h4>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Reputation Class:</span>
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
                  {selectedReputation.medianMfe != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Median MFE:</span>
                      <span className="font-mono text-emerald-400">{selectedReputation.medianMfe}x</span>
                    </div>
                  )}
                  {selectedReputation.medianMae != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Median MAE:</span>
                      <span className="font-mono text-rose-400">{selectedReputation.medianMae}x</span>
                    </div>
                  )}
                  {selectedReputation.creatorRealizedPnl != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Creator PnL:</span>
                      <span className="font-mono text-slate-200">${selectedReputation.creatorRealizedPnl}</span>
                    </div>
                  )}
                  {selectedReputation.bundleSniperAssociation != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Bundle/Sniper Risk:</span>
                      <span className="font-mono text-amber-400">
                        {selectedReputation.bundleSniperAssociation ? "ASSOCIATED" : "CLEAN"}
                      </span>
                    </div>
                  )}
                  {selectedReputation.sharedFunderRecurrence != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Shared Funder Cluster:</span>
                      <span className="font-mono text-amber-400">
                        {selectedReputation.sharedFunderRecurrence ? "RECURRING" : "ISOLATED"}
                      </span>
                    </div>
                  )}
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
              Path Hops ({pathResult.nodes.length - 1} hops) — Highlighted on Graph Above
            </h4>
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              {pathResult.nodes.map((nodeId, idx) => (
                <span key={nodeId} className="flex items-center gap-2">
                  <span className="bg-slate-900 border border-amber-500/40 text-amber-300 px-2 py-1 rounded">
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
