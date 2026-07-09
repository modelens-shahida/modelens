import { useEffect, useRef, useCallback, useState } from "react";
import toast from "react-hot-toast";

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000`
    : "ws://localhost:8000");

const EVENT_MESSAGES = {
  "job.completed": "✅ AI generation job completed!",
  "job.failed": "❌ AI generation job failed.",
  "training_done": "🎉 Character training completed!",
  "asset.processed": "📁 Asset processed successfully.",
  "low_credit": "⚠️ Your credit balance is low.",
  "webhook_failed": "🔔 Webhook delivery failed.",
};

export function useWebSocket({ token, brandId, onEvent } = {}) {
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);

  const connect = useCallback(() => {
    if (!token || !brandId) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE_URL}/api/v1/ws/events?token=${token}&brand_id=${brandId}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log("[WebSocket] Connected to real-time events");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "ping") {
            ws.send(JSON.stringify({ type: "pong" }));
            return;
          }

          if (data.type === "connected") {
            console.log("[WebSocket] Handshake complete");
            return;
          }

          setLastEvent(data);

          // Show toast notification
          const message = EVENT_MESSAGES[data.type];
          if (message) {
            if (data.type === "job.failed" || data.type === "webhook_failed") {
              toast.error(message);
            } else if (data.type === "low_credit") {
              toast(message, { icon: "⚠️" });
            } else {
              toast.success(message);
            }
          }

          // Call custom event handler
          if (onEvent) {
            onEvent(data);
          }
        } catch (err) {
          console.error("[WebSocket] Failed to parse message:", err);
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        console.log("[WebSocket] Disconnected. Reconnecting in 5s...");
        // Auto-reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 5000);
      };

      ws.onerror = (err) => {
        console.error("[WebSocket] Error:", err);
        ws.close();
      };
    } catch (err) {
      console.error("[WebSocket] Connection failed:", err);
    }
  }, [token, brandId, onEvent]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected, lastEvent, sendMessage, disconnect };
}
