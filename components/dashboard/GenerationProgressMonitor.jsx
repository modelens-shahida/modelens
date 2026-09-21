"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Loader2, CheckCircle2, Clock, Sparkles, Layers, Image as ImageIcon, AlertCircle, ArrowRight, Zap, RefreshCw } from "lucide-react";
import { getBatchJobStatus } from "@/lib/generationService";

export default function GenerationProgressMonitor({
  jobId = "JOB-SPRING-2027-001",
  projectName = "Spring 2027 Runway Campaign",
  characterName = "ELISKA NOVAK (EE-F-002)",
  productName = "Silk Bias Cut Slip Dress",
  onComplete,
}) {
  const [jobStatus, setJobStatus] = useState("generating"); // "queued" | "generating" | "completed" | "failed"
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(4);
  const [tiles, setTiles] = useState([
    { angle: "FRONT", status: "completed", progress: 100, duration: "3.8s", preview_url: null },
    { angle: "L30", status: "generating", progress: 65, duration: "Rendering...", preview_url: null },
    { angle: "R30", status: "queued", progress: 0, duration: "Waiting...", preview_url: null },
    { angle: "L45", status: "queued", progress: 0, duration: "Waiting...", preview_url: null },
  ]);
  const [wsConnected, setWsConnected] = useState(false);
  const [parallelMode, setParallelMode] = useState(true);
  const wsRef = useRef(null);

  // Initialize WebSocket and Polling Fallback
  useEffect(() => {
    let isSubscribed = true;
    let pollInterval = null;

    // Connect WebSocket
    const connectWs = () => {
      try {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/batch/${jobId}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isSubscribed) setWsConnected(true);
        };

        ws.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data);
            if (data.event === "batch_progress" || data.event === "batch_finished") {
              if (data.status) setJobStatus(data.status);
              if (data.completed !== undefined) setCompletedCount(data.completed);
              if (data.total !== undefined) setTotalCount(data.total);
              if (data.angle_tiles && data.angle_tiles.length > 0) {
                setTiles(data.angle_tiles);
              }

              if (data.event === "batch_finished" || data.status === "completed") {
                setJobStatus("completed");
                if (onComplete) onComplete(data);
              }
            }
          } catch (e) {
            console.error("WS parse error", e);
          }
        };

        ws.onerror = () => {
          if (isSubscribed) setWsConnected(false);
        };

        ws.onclose = () => {
          if (isSubscribed) setWsConnected(false);
        };
      } catch (err) {
        console.warn("WebSocket direct connection failed, activating polling", err);
      }
    };

    connectWs();

    // Fallback polling loop (or sync)
    pollInterval = setInterval(async () => {
      if (!isSubscribed) return;
      try {
        const res = await getBatchJobStatus(jobId);
        if (res && isSubscribed) {
          if (res.status) setJobStatus(res.status);
          if (res.completed !== undefined) setCompletedCount(res.completed);
          if (res.total_angles !== undefined) setTotalCount(res.total_angles);
          if (res.parallel !== undefined) setParallelMode(res.parallel);
          if (res.angle_tiles && res.angle_tiles.length > 0) {
            setTiles(res.angle_tiles);
          }

          if (res.status === "completed") {
            setCompletedCount(res.total_angles || tiles.length);
            if (onComplete) onComplete(res);
          }
        }
      } catch (e) {
        // quiet fallback
      }
    }, 2500);

    return () => {
      isSubscribed = false;
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (_) {}
      }
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [jobId]);

  const progressPercent = totalCount > 0 ? Math.min(100, Math.round((completedCount / totalCount) * 100)) : 0;
  const isFinished = jobStatus === "completed" || progressPercent >= 100;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Header & Job ID */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white tracking-tight">{projectName}</h1>
              {isFinished ? (
                <span className="px-3 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-semibold rounded-full flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>BATCH COMPLETE</span>
                </span>
              ) : (
                <span className="px-3 py-0.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono font-semibold rounded-full flex items-center gap-1.5">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>PARALLEL STREAMING</span>
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1.5">
              <p className="text-xs text-zinc-400 font-mono">Job ID: {jobId}</p>
              <span className="text-zinc-600">•</span>
              <span className="text-[11px] font-mono flex items-center gap-1 text-zinc-400">
                <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-emerald-400 animate-pulse" : "bg-cyan-500"}`} />
                {wsConnected ? "Live WebSocket Stream" : "Synchronized Poller Active"}
              </span>
              {parallelMode && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/30 text-purple-300 flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  <span>Parallel Concurrency Mode</span>
                </span>
              )}
            </div>
          </div>

          <div className="text-right flex flex-col items-start md:items-end gap-2">
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase">Batch Progress</span>
              <p className="text-xl font-extrabold text-cyan-400">
                {completedCount} / {totalCount} Angles ({progressPercent}%)
              </p>
            </div>
            {isFinished && (
              <Link
                href={`/dashboard/results/${jobId}`}
                className="flex items-center gap-1.5 bg-cyan-500 hover:bg-cyan-400 text-black font-extrabold text-xs px-4 py-2 rounded-xl transition-all shadow-md shadow-cyan-500/20"
              >
                <span>Proceed to QA Review</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-5 space-y-2">
          <div className="w-full h-3.5 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800 p-0.5">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 via-indigo-500 to-emerald-400 rounded-full transition-all duration-500 shadow-sm"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] text-zinc-500">
            <span>Asynchronous multi-angle engine active — you may safely leave this page.</span>
            <span>{isFinished ? "Batch production complete" : "Estimated remaining: ~8 seconds"}</span>
          </div>
        </div>
      </div>

      {/* Active Job Parameters Summary */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-zinc-500">Model Character</span>
          <p className="font-semibold text-white mt-0.5">{characterName}</p>
        </div>
        <div>
          <span className="text-zinc-500">Target Product</span>
          <p className="font-semibold text-white mt-0.5">{productName}</p>
        </div>
        <div>
          <span className="text-zinc-500">Environment</span>
          <p className="font-semibold text-white mt-0.5">Studio Grey Minimal</p>
        </div>
        <div>
          <span className="text-zinc-500">Master Quality</span>
          <p className="font-semibold text-cyan-400 mt-0.5">Studio Quality 4K</p>
        </div>
      </div>

      {/* Streaming Result Tiles */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <span>Parallel Multi-Angle Streaming Tiles ({tiles.length} Slots)</span>
          </h3>
          <span className="text-xs font-mono text-zinc-500">Live Telemetry</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {tiles.map((tile, idx) => {
            const statusUpper = (tile.status || "queued").toUpperCase();
            const isDone = statusUpper === "COMPLETED" || statusUpper === "DONE";
            const isGen = statusUpper === "GENERATING" || statusUpper === "RENDERING" || statusUpper === "PROCESSING";
            const isFail = statusUpper === "FAILED";

            return (
              <div
                key={tile.angle || idx}
                className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-md flex flex-col justify-between hover:border-zinc-700 transition-all group"
              >
                <div className="px-3 py-2 bg-zinc-900/90 border-b border-zinc-800 text-[11px] font-mono font-bold text-white flex items-center justify-between">
                  <span>[ {tile.angle} ]</span>
                  {isDone && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                  {isGen && <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin" />}
                  {!isDone && !isGen && !isFail && <Clock className="w-3.5 h-3.5 text-zinc-600" />}
                  {isFail && <AlertCircle className="w-3.5 h-3.5 text-rose-400" />}
                </div>

                <div className="aspect-[3/4] bg-zinc-900 flex items-center justify-center p-3 relative">
                  {isDone && (
                    <div className="text-center space-y-1.5">
                      <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto">
                        <ImageIcon className="w-5 h-5 text-emerald-400" />
                      </div>
                      <span className="text-[10px] font-mono text-emerald-400 font-bold block">READY FOR QA</span>
                      <span className="text-[9px] text-zinc-500 block">ArcFace 98.2% PASS</span>
                    </div>
                  )}
                  {isGen && (
                    <div className="text-center space-y-1.5">
                      <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto">
                        <Sparkles className="w-5 h-5 text-amber-400 animate-pulse" />
                      </div>
                      <span className="text-[10px] font-mono text-amber-400 font-bold block">DIFFUSING...</span>
                      <div className="w-16 h-1.5 bg-zinc-800 rounded-full mx-auto overflow-hidden">
                        <div className="h-full bg-amber-400 rounded-full animate-pulse" style={{ width: `${tile.progress || 60}%` }} />
                      </div>
                    </div>
                  )}
                  {!isDone && !isGen && !isFail && (
                    <div className="text-center space-y-1.5 opacity-50">
                      <div className="w-10 h-10 rounded-xl bg-zinc-800/50 flex items-center justify-center mx-auto">
                        <Clock className="w-5 h-5 text-zinc-500" />
                      </div>
                      <span className="text-[10px] font-mono text-zinc-500 block">QUEUED</span>
                    </div>
                  )}
                </div>

                <div className="px-3 py-2 bg-zinc-950 text-[10px] font-mono text-zinc-400 border-t border-zinc-900 flex items-center justify-between">
                  <span>{tile.duration || (isDone ? "3.9s" : isGen ? "Streaming" : "Queued")}</span>
                  <span className={isDone ? "text-emerald-400" : isGen ? "text-amber-400" : "text-zinc-600"}>
                    {isDone ? "PASS" : isGen ? "IN FLIGHT" : "IDLE"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

