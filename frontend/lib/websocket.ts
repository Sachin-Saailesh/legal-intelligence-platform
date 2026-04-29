"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWsUrl } from "./api";

export type WsFrame =
  | { type: "agent_start"; agent: string }
  | { type: "agent_complete"; agent: string }
  | { type: "intent_classified"; intent: string }
  | { type: "chunk"; text: string }
  | { type: "citation"; chunk: Record<string, unknown> }
  | { type: "complete"; confidence: number; requires_review: boolean; review_reason?: string | null }
  | { type: "error"; message: string }
  | { type: "ping" };

interface UseAgentStreamOptions {
  onFrame?: (frame: WsFrame) => void;
  maxRetries?: number;
}

export function useAgentStream(sessionId: string | null, options: UseAgentStreamOptions = {}) {
  const { onFrame, maxRetries = 5 } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDoneRef = useRef(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const markDone = useCallback(() => {
    isDoneRef.current = true;
    setIsDone(true);
  }, []);

  const connect = useCallback(() => {
    if (!sessionId || isDoneRef.current) return;

    const url = getWsUrl(`/api/queries/${sessionId}/stream`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const frame: WsFrame = JSON.parse(event.data);
        if (frame.type === "ping") return;
        onFrame?.(frame);
        if (frame.type === "complete" || frame.type === "error") {
          markDone();
          ws.close();
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Use ref (not state) to avoid stale closure after complete/error fires
      if (!isDoneRef.current && retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current++;
        timerRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [sessionId, onFrame, maxRetries, markDone]);

  useEffect(() => {
    isDoneRef.current = false;
    connect();
    return () => {
      timerRef.current && clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const close = useCallback(() => {
    markDone();
    wsRef.current?.close();
  }, [markDone]);

  return { isConnected, isDone, close };
}
