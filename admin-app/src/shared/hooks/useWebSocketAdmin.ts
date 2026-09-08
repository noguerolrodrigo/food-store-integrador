import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

const WS_BASE = "ws://localhost:8000";

/**
 * Hook que conecta al WebSocket de administración y refresca los pedidos
 * cuando llegan eventos en tiempo real.
 */
export function useWebSocketAdmin(token: string | null) {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!token) return;

    let active = true;

    function connect() {
      if (!active) return;

      if (wsRef.current) {
        wsRef.current.close();
      }

      const url = `${WS_BASE}/ws/pedidos?token=${token}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[WS Admin] Conectado");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>;
          console.log("[WS Admin] Evento recibido:", data);
          queryClient.invalidateQueries({ queryKey: ["pedidos"] });
          queryClient.invalidateQueries({ queryKey: ["pedido", data.pedido_id] });
          queryClient.invalidateQueries({ queryKey: ["pedido-historial", data.pedido_id] });
        } catch {
          // ignorar
        }
      };

      ws.onclose = () => {
        if (!active) return; // cierre intencional: no reconectar
        console.log("[WS Admin] Desconectado, reconectando en 5s...");
        reconnectTimeoutRef.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      active = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [token, queryClient]);
}