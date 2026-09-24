import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000`
    : "ws://localhost:8000");

/**
 * useGenerationProgress Hook
 * Connects to /api/v1/ws/generation/{jobId}/progress for real-time progress & step updates.
 */
export function useGenerationProgress({ jobId, brandId, token, onComplete, onError, enabled = true } = {}) {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(null);
  const [stepLabel, setStepLabel] = useState("");
  const [status, setStatus] = useState("idle"); // idle, connecting, running, completed, failed
  const [error, setError] = useState(null);
  const [eventHistory, setEventHistory] = useState([]);

  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
  }, [onComplete, onError]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (!enabled || !jobId || !brandId || !token) {
      return;
    }

    setStatus("connecting");
    const wsUrl = `${WS_BASE_URL}/api/v1/ws/generation/${encodeURIComponent(jobId)}/progress?token=${encodeURIComponent(token)}&brand_id=${encodeURIComponent(brandId)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setStatus("running");
        console.log(`[GenerationWS] Connected for job ${jobId}`);
      };

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          setEventHistory((prev) => [...prev.slice(-19), data]);

          if (data.event === "generation.progress" || data.event === "generation.step") {
            if (data.percent !== undefined) setProgress(data.percent);
            if (data.step) setCurrentStep(data.step);
            if (data.step_label) setStepLabel(data.step_label);
          } else if (data.event === "generation.completed") {
            setProgress(100);
            setStatus("completed");
            if (onCompleteRef.current) onCompleteRef.current(data);
          } else if (data.event === "generation.failed") {
            setStatus("failed");
            setError(data.reason || "Generation failed");
            if (onErrorRef.current) onErrorRef.current(data);
          }
        } catch (err) {
          console.warn("[GenerationWS] Message parsing error:", err);
        }
      };

      ws.onerror = (err) => {
        console.warn("[GenerationWS] WebSocket error:", err);
      };

      ws.onclose = (evt) => {
        setIsConnected(false);
        console.log(`[GenerationWS] Disconnected (code: ${evt.code})`);
      };

      return () => {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close();
        }
      };
    } catch (err) {
      console.warn("[GenerationWS] Setup failed, falling back:", err);
      setStatus("running");
    }
  }, [jobId, brandId, token, enabled]);

  return {
    isConnected,
    progress,
    currentStep,
    stepLabel,
    status,
    error,
    eventHistory,
    disconnect,
  };
}
