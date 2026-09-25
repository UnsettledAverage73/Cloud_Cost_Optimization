import { useState, useEffect, useRef, useCallback } from 'react';

export interface TelemetryDatapoint {
  timestamp: string;
  cpu: number;
  mem: number;
  disk: number;
  net_in_bytes: number;
  net_out_bytes: number;
  packets_in: number;
  packets_out: number;
  cpu_credits?: number;
  is_guest_agent?: boolean;
}

export function useRealtimeTelemetry(instanceId: string | null | undefined, maxPoints = 60, apiUrl?: (p: string) => string) {
  const [points, setPoints] = useState<TelemetryDatapoint[]>([]);
  const [isLive, setIsLive] = useState(false);
  const [connectionMode, setConnectionMode] = useState<'websocket' | 'rest_polling' | 'disconnected'>('disconnected');
  const [cwAgentEnabled, setCwAgentEnabled] = useState(true);
  const [timeframe, setTimeframe] = useState<'1h' | '3h' | '12h' | '1d' | '3d' | '1w'>('1h');
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fallback REST fetcher if WebSocket fails
  const fetchRestFallback = useCallback(async (id: string) => {
    try {
      const endpoint = apiUrl ? apiUrl(`/api/v2/telemetry/${id}/live`) : `/api/v2/telemetry/${id}/live`;
      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.datapoints) && data.datapoints.length > 0) {
          setPoints(data.datapoints.slice(-maxPoints));
          setIsLive(true);
          setConnectionMode('rest_polling');
        }
      }
    } catch {
      // Ignore background fallback errors
    }
  }, [apiUrl, maxPoints]);

  useEffect(() => {
    if (!instanceId) {
      setPoints([]);
      setIsLive(false);
      setConnectionMode('disconnected');
      return;
    }

    const currentId = instanceId;
    let isSubscribed = true;

    function connectWs() {
      if (!isSubscribed) return;

      try {
        const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        
        let wsHost = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
        if (process.env.NEXT_PUBLIC_WS_URL) {
          wsHost = process.env.NEXT_PUBLIC_WS_URL.replace(/^https?:\/\//, '').replace(/^wss?:\/\//, '');
        } else if (process.env.NEXT_PUBLIC_API_URL) {
          wsHost = process.env.NEXT_PUBLIC_API_URL.replace(/^https?:\/\//, '').replace(/^wss?:\/\//, '');
        }

        const wsUrl = `${protocol}//${wsHost}/ws/telemetry/${currentId}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!isSubscribed) {
            ws.close();
            return;
          }
          setIsLive(true);
          setConnectionMode('websocket');
          // Clear any polling fallback if active
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
        };

        ws.onmessage = (event) => {
          if (!isSubscribed) return;
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'HISTORY' && Array.isArray(msg.datapoints)) {
              setPoints(msg.datapoints.slice(-maxPoints));
            } else if (msg.type === 'TICK' && msg.datapoint) {
              setPoints((prev) => {
                const updated = [...prev, msg.datapoint];
                return updated.length > maxPoints ? updated.slice(updated.length - maxPoints) : updated;
              });
            }
          } catch {
            // ignore JSON parse error
          }
        };

        ws.onclose = () => {
          if (!isSubscribed) return;
          setIsLive(false);
          // If websocket closes, attempt reconnect after 3 seconds, and start REST polling
          if (!pollingIntervalRef.current) {
            fetchRestFallback(currentId);
            pollingIntervalRef.current = setInterval(() => fetchRestFallback(currentId), 3000);
          }
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isSubscribed) connectWs();
          }, 4000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        // Fallback to REST polling
        fetchRestFallback(currentId);
        if (!pollingIntervalRef.current) {
          pollingIntervalRef.current = setInterval(() => fetchRestFallback(currentId), 3000);
        }
      }
    }

    connectWs();

    return () => {
      isSubscribed = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [instanceId, maxPoints, fetchRestFallback]);

  return {
    points,
    isLive,
    connectionMode,
    cwAgentEnabled,
    setCwAgentEnabled,
    timeframe,
    setTimeframe,
    latestPoint: points.length > 0 ? points[points.length - 1] : null,
  };
}
