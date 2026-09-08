import apiClient from "../../../shared/services/apiClient";
import type { PreferenceResponse, PagoStatusResponse } from "../types/payment.types";

export const createPreference = async (
  pedido_id: number
): Promise<PreferenceResponse> => {
  const { data } = await apiClient.post(
    "/api/v1/pagos/create-preference",
    { pedido_id }
  );
  return data;
};

export const getPaymentStatus = async (
  pedido_id: number
): Promise<PagoStatusResponse> => {
  const { data } = await apiClient.get(`/api/v1/pagos/${pedido_id}`);
  return data;
};

/** Pide al backend que verifique un pago contra la API de MP (mismo flujo que el webhook). */
export async function verifyPayment(payment_id: string) {
  const { data } = await apiClient.get("/api/v1/pagos/webhook", {
    params: { id: payment_id, topic: "payment" },
  });
  return data;
}