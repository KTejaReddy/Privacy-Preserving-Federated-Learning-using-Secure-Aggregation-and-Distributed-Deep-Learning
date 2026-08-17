import { useEffect, useRef, useState } from "react";

export interface WsEvent {
  event: string;
  data: Record<string, unknown>;
}

/** Subscribes to the platform's realtime WebSocket feed (FastAPI ws://). */
export function useRealtime(onEvent?: (ev: WsEvent) => void): { connected: boolean; lastEvent: WsEvent | null } {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/api/v1/monitor/ws`;
    let ws: WebSocket | null = null;
    let retry = 0;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(url);
      ws.onopen = () => {
        setConnected(true);
        retry = 0;
      };
      ws.onmessage = (msg) => {
        try {
          const ev = JSON.parse(msg.data) as WsEvent;
          setLastEvent(ev);
          cbRef.current?.(ev);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          retry += 1;
          setTimeout(connect, Math.min(1000 * retry, 8000));
        }
      };
      ws.onerror = () => ws?.close();
    };
    connect();

    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  return { connected, lastEvent };
}

/** Periodic poller fallback: refetches a query every N ms. */
export function useTick(intervalMs = 3000) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), intervalMs);
    return () => clearInterval(iv);
  }, [intervalMs]);
}
