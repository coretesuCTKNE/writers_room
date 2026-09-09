import { useEffect } from 'react';

import { getAuthToken } from './firebase';
import type { AgentStatusValue } from './store-agent';

interface AgentMessage {
  agent: string;
  status: AgentStatusValue;
  message?: string;
  ts?: number;
}

const MAX_ATTEMPTS = 6;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30_000;

export function useAgentWebSocket(onMessage: (data: AgentMessage) => void): void {
  useEffect(() => {
    let ws: WebSocket | null = null;
    let attempt = 0;
    let cancelled = false;
    let timer: number | null = null;

    const connect = (): void => {
      if (cancelled) return;
      // Firebase Hosting rewrites do not proxy WebSockets — prod builds bake
      // VITE_WS_BASE (direct Cloud Run origin). Dev falls back to same-origin
      // (Vite proxy handles /api on :5173).
      void (async () => {
        const wsBase = import.meta.env.VITE_WS_BASE as string | undefined;
        const base = wsBase ?? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
        const token = await getAuthToken();
        const auth = token ? `?token=${encodeURIComponent(token)}` : '';
        const url = `${base}/api/ws/agents${auth}`;
        if (cancelled) return;
        ws = new WebSocket(url);
        wire();
      })();
    };

    const wire = (): void => {
      if (!ws) return;
      ws.onmessage = (event) => {
        if (typeof event.data !== 'string') return;
        try {
          const data = JSON.parse(event.data) as AgentMessage;
          if (data.agent && data.status) {
            attempt = 0;
            onMessage(data);
          }
        } catch {
          // ignore malformed payloads
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        attempt = Math.min(attempt + 1, MAX_ATTEMPTS);
        const delay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
        timer = window.setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
      ws?.close();
    };
  }, [onMessage]);
}
