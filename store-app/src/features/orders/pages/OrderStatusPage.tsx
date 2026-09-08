
import { useState, useEffect } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { usePaymentStatus } from "../../pagos";
import { useWebSocketOrder } from "../../../shared/hooks/useWebSocketOrder";
import { Button } from "../../../shared/ui/Button";
import { Alert } from "../../../shared/ui/Alert";
import { useQueryClient } from "@tanstack/react-query";
import { verifyPayment } from "../../pagos/services/paymentService";

/* ─── Status Config ─── */
const STATUS_CONFIG: Record<
  string,
  {
    title: string;
    color: string;
    border: string;
    icon: React.ReactNode;
  }
> = {
  approved: {
    title: "Pago aprobado",
    color: "text-emerald-400",
    border: "border-emerald-500/20",
    icon: (
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/10 border-2 border-emerald-500/20">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="36"
          height="36"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-emerald-400"
        >
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      </div>
    ),
  },
  rejected: {
    title: "Pago rechazado",
    color: "text-red-400",
    border: "border-red-500/20",
    icon: (
      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-red-500/10 border-2 border-red-500/20">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="36"
          height="36"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-red-400"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      </div>
    ),
  },
  pending: {
    title: "Pago pendiente",
    color: "text-amber-400",
    border: "border-amber-500/20",
    icon: (
      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-amber-500/10 border-2 border-amber-500/20">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="36"
          height="36"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-amber-400"
        >
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      </div>
    ),
  },
};

export default function OrderStatusPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const status = searchParams.get("status") || "pending";
  const pedidoId = id ? Number(id) : null;

  const { data: pago, isLoading, isError } = usePaymentStatus(pedidoId);
  const { lastEvent: wsEvent, status: wsStatus } = useWebSocketOrder(pedidoId);
  const [wsConfirmed, setWsConfirmed] = useState(false);

  const queryClient = useQueryClient();
  const paymentId = searchParams.get("payment_id");

  // Al volver de MP, verificamos el pago contra su API sin esperar el webhook.
  useEffect(() => {
    if (!paymentId || !pedidoId) return;
    verifyPayment(paymentId)
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ["pago-status", pedidoId] });
        queryClient.invalidateQueries({ queryKey: ["mis-pedidos"] });
      })
      .catch(() => {
        // si falla, el webhook o el polling lo resuelven después
      });
  }, [paymentId, pedidoId, queryClient]);

  useEffect(() => {
    if (wsEvent?.event === "pago_confirmado" || wsEvent?.event === "estado_cambiado") {
      setWsConfirmed(true);
    }
  }, [wsEvent]);

  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;

  return (
    <div className="mx-auto max-w-lg px-4 py-16 sm:px-6">
      {/* Status card */}
      <div
        className={`rounded-2xl border ${config.border} bg-gradient-to-b ${status === "approved" ? "from-emerald-500/5" : status === "rejected" ? "from-red-500/5" : "from-amber-500/5"} to-transparent p-8 text-center shadow-xl`}
      >
        {config.icon}

        <h1 className={`mt-6 text-2xl font-bold ${config.color}`}>
          {config.title}
        </h1>

        <p className="mt-2 text-sm text-zinc-500">
          Pedido #{pedidoId}
        </p>

        {/* WebSocket en vivo indicator */}
        <div className="mt-3 flex items-center justify-center gap-1.5">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              wsStatus === "connected"
                ? "bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse"
                : wsStatus === "connecting"
                  ? "bg-amber-500"
                  : "bg-zinc-600"
            }`}
          />
          <span className="text-[10px] text-zinc-600">
            {wsStatus === "connected"
              ? "Tiempo real activo"
              : wsStatus === "connecting"
                ? "Conectando..."
                : "Sin conexión en vivo"}
          </span>
        </div>

        {/* WebSocket confirmación inmediata */}
        {wsConfirmed && (
          <div className="mt-4">
            <Alert variant="success">
              ¡Pago confirmado en tiempo real! Tu pedido ya está en proceso.
            </Alert>
          </div>
        )}

        {/* Polling status */}
        {isLoading && (
          <div className="mt-6 flex items-center justify-center gap-2 text-sm text-zinc-500">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-300" />
            Consultando estado del pago...
          </div>
        )}

        {isError && (
          <div className="mt-6">
            <Alert variant="info">
              El pago se está procesando. El estado se actualizará automáticamente.
            </Alert>
          </div>
        )}

        {pago && (
          <div className="mt-8 space-y-3 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-5 text-left">
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-500">Estado MP</span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${
                  pago.mp_status === "approved"
                    ? "bg-emerald-500/10 text-emerald-400"
                    : pago.mp_status === "rejected"
                      ? "bg-red-500/10 text-red-400"
                      : "bg-amber-500/10 text-amber-400"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    pago.mp_status === "approved"
                      ? "bg-emerald-400"
                      : pago.mp_status === "rejected"
                        ? "bg-red-400"
                        : "bg-amber-400"
                  }`}
                />
                {pago.mp_status === "approved"
                  ? "Aprobado"
                  : pago.mp_status === "rejected"
                    ? "Rechazado"
                    : pago.mp_status === "pending"
                      ? "Pendiente"
                      : pago.mp_status}
              </span>
            </div>
            {pago.mp_status_detail && (
              <div className="flex items-center justify-between border-t border-zinc-800/60 pt-3">
                <span className="text-sm text-zinc-500">Detalle</span>
                <span className="text-sm text-zinc-300">
                  {pago.mp_status_detail}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between border-t border-zinc-800/60 pt-3">
              <span className="text-sm text-zinc-500">Monto</span>
              <span className="text-lg font-bold text-zinc-100">
                ${Number(pago.transaction_amount).toFixed(2)}
              </span>
            </div>
          </div>
        )}

        {pago?.mp_status === "approved" && (
          <div className="mt-4">
            <Alert variant="success">
              ¡Pago confirmado! Tu pedido ya está en proceso.
            </Alert>
          </div>
        )}

        {pago?.mp_status === "rejected" && (
          <div className="mt-4">
            <Alert variant="error">
              El pago fue rechazado. Podés intentar pagar nuevamente desde
              "Mis Pedidos".
            </Alert>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="mt-8 flex flex-col gap-3">
        <Link to="/mis-pedidos">
          <Button size="xl" className="w-full" variant="dark">
            Mis pedidos
          </Button>
        </Link>
        <Link to="/">
          <Button size="xl" className="w-full">
            Seguir comprando
          </Button>
        </Link>
      </div>
    </div>
  );
}
