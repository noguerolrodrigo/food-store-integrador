import { useQuery } from "@tanstack/react-query";
import { getPedidoById, getHistorialPedido } from "../services/pedido";
import { getApiErrorMessage } from "../../../shared/services/apiError";
import { ESTADO_COLORS, ESTADO_LABELS } from "./kanbanConfig";

interface OrderDetailModalProps {
  isOpen: boolean;
  pedidoId: number | null;
  onClose: () => void;
}

export const OrderDetailModal = ({
  isOpen,
  pedidoId,
  onClose,
}: OrderDetailModalProps) => {
  const {
    data: pedido,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["pedido", pedidoId],
    queryFn: () => (pedidoId ? getPedidoById(pedidoId) : null),
    enabled: isOpen && !!pedidoId,
  });

  const { data: historial } = useQuery({
    queryKey: ["pedido-historial", pedidoId],
    queryFn: () => (pedidoId ? getHistorialPedido(pedidoId) : null),
    enabled: isOpen && !!pedidoId,
  });

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl text-white">
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg bg-red-500/20 px-3 py-1 text-sm font-medium text-red-400 transition hover:bg-red-500/30"
        >
          ✕
        </button>

        {/* Loading state */}
        {isLoading && (
          <div className="flex flex-col gap-4 py-8">
            <div className="h-6 w-48 animate-pulse rounded bg-zinc-800" />
            <div className="h-4 w-32 animate-pulse rounded bg-zinc-800" />
            <div className="mt-4 grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-zinc-800" />
              ))}
            </div>
            <div className="mt-4 h-32 animate-pulse rounded bg-zinc-800" />
          </div>
        )}

        {/* Error state */}
        {isError && !isLoading && (
          <div className="flex flex-col items-center gap-3 py-8">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="36"
              height="36"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-red-400"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p className="text-sm text-red-400">
              {getApiErrorMessage(error)}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-1.5 text-sm text-gray-300 hover:bg-zinc-700"
            >
              Cerrar
            </button>
          </div>
        )}

        {/* Content */}
        {pedido && (
          <div className="space-y-5">
            {/* Header */}
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h2 className="text-xl font-bold">{pedido.numero_pedido}</h2>
                <span
                  className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${ESTADO_COLORS[pedido.estado]}`}
                >
                  {ESTADO_LABELS[pedido.estado]}
                </span>
              </div>
              <p className="text-xs text-gray-500">
                {new Date(pedido.created_at).toLocaleString()}
              </p>
            </div>

            {/* Info grid */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-2.5 rounded-lg bg-zinc-800/50 p-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Usuario ID:</span>
                <span>{pedido.usuario_id}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Forma de pago:</span>
                <span className="capitalize">
                  {pedido.forma_pago.replace(/_/g, " ").toLowerCase()}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Total:</span>
                <span className="font-semibold text-emerald-400">
                  ${Number(pedido.monto_total).toFixed(2)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Actualizado:</span>
                <span className="text-xs">
                  {new Date(pedido.updated_at).toLocaleString()}
                </span>
              </div>
              <div className="col-span-2 flex items-start gap-2">
                <span className="text-gray-500 shrink-0">Dirección:</span>
                <span>{pedido.direccion_entrega}</span>
              </div>
              {pedido.observaciones && (
                <div className="col-span-2 flex items-start gap-2">
                  <span className="text-gray-500 shrink-0">Observaciones:</span>
                  <span className="italic text-gray-300">
                    {pedido.observaciones}
                  </span>
                </div>
              )}
            </div>

            {/* Items table */}
            {pedido.detalles && pedido.detalles.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-300">
                  Productos
                </h3>
                <div className="overflow-x-auto rounded-lg border border-zinc-700">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-700 bg-zinc-800 text-left text-xs text-gray-500">
                        <th className="p-2.5">Producto</th>
                        <th className="p-2.5 text-right">Cant</th>
                        <th className="p-2.5 text-right">P/U</th>
                        <th className="p-2.5 text-right">Subtotal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pedido.detalles.map((d) => (
                        <tr
                          key={d.id}
                          className="border-b border-zinc-800 last:border-b-0 hover:bg-zinc-800/50"
                        >
                          <td className="p-2.5">{d.nombre_producto}</td>
                          <td className="p-2.5 text-right">{d.cantidad}</td>
                          <td className="p-2.5 text-right">
                            ${Number(d.precio_unitario).toFixed(2)}
                          </td>
                          <td className="p-2.5 text-right font-medium text-emerald-400">
                            ${Number(d.subtotal).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* State history timeline */}
            {historial && historial.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-300">
                  Historial de Estados
                </h3>
                <div className="relative space-y-0">
                  {historial.map((h, index) => (
                    <div key={h.id} className="flex gap-3 pb-4 last:pb-0">
                      {/* Timeline line */}
                      <div className="flex flex-col items-center">
                        <span
                          className={`inline-flex h-3 w-3 shrink-0 rounded-full ${
                            index === historial.length - 1
                              ? "bg-emerald-500 ring-2 ring-emerald-500/30"
                              : "bg-zinc-600"
                          }`}
                        />
                        {index < historial.length - 1 && (
                          <div className="mt-1 h-full w-0.5 bg-zinc-700" />
                        )}
                      </div>
                      {/* Content */}
                      <div className="flex-1 pb-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${ESTADO_COLORS[h.estado_nuevo]}`}
                          >
                            {ESTADO_LABELS[h.estado_nuevo]}
                          </span>
                          <span className="text-[10px] text-gray-500">
                            {new Date(h.created_at).toLocaleString()}
                          </span>
                        </div>
                        {h.razon && (
                          <p className="mt-0.5 text-xs text-gray-400">
                            {h.razon}
                          </p>
                        )}
                        {h.usuario_id && (
                          <p className="text-[10px] text-gray-600">
                            por usuario #{h.usuario_id}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
