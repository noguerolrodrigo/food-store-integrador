import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import mercadopago

from app.core.config import settings
from app.modules.pagos.model import Pago
from app.modules.pagos.pagos_uow import PagoUnitOfWork
from app.modules.pagos.schema import PagoCreate
from app.modules.pedido.models import EstadoPedido, HistorialEstadoPedido, Pedido


def get_mp_sdk() -> mercadopago.SDK:
    return mercadopago.SDK(settings.mp_access_token)


class PagoService:
    def __init__(self, uow: PagoUnitOfWork):
        self.uow = uow

    def crear_pago(self, data: PagoCreate, usuario_id: int) -> Pago:
        pedido = self.uow.session.get(Pedido, data.pedido_id)
        if not pedido:
            raise ValueError(f"Pedido {data.pedido_id} no encontrado")
        if pedido.estado != EstadoPedido.PENDIENTE:
            raise ValueError(
                f"Solo se puede pagar un pedido PENDIENTE (estado actual: {pedido.estado})"
            )

        pago_existente = self.uow.pagos.get_by_pedido_id(data.pedido_id)
        if pago_existente and pago_existente.mp_status == "approved":
            raise ValueError("Este pedido ya tiene un pago aprobado")

        idempotency_key = str(uuid.uuid4())
        external_reference = str(data.pedido_id)

        sdk = get_mp_sdk()
        mp_response = sdk.payment().create(
            {
                "transaction_amount": float(pedido.monto_total),
                "token": data.token,
                "description": f"Pedido {pedido.numero_pedido}",
                "installments": data.installments,
                "payment_method_id": data.payment_method_id,
                "issuer_id": data.issuer_id,
                "external_reference": external_reference,
                "notification_url": settings.mp_notification_url,
            },
            {"X-Idempotency-Key": idempotency_key},
        )

        response_body = mp_response.get("response", {})
        mp_status = response_body.get("status", "pending")

        pago = Pago(
            pedido_id=data.pedido_id,
            mp_payment_id=response_body.get("id"),
            mp_status=mp_status,
            mp_status_detail=response_body.get("status_detail"),
            transaction_amount=Decimal(str(response_body.get("transaction_amount", pedido.monto_total))),
            payment_method_id=response_body.get("payment_method_id", data.payment_method_id),
            external_reference=external_reference,
            idempotency_key=idempotency_key,
        )
        self.uow.pagos.add(pago)

        if mp_status == "approved":
            self._confirmar_pedido(pedido)

        return pago

    def procesar_webhook(
        self, payload: dict
    ) -> Optional[tuple[Pago, int, Optional[EstadoPedido]]]:
        if payload.get("type") != "payment":
            return None

        payment_id = int(payload["data"]["id"])

        sdk = get_mp_sdk()
        mp_response = sdk.payment().get(payment_id)

        # Verificar que la API de MP respondió OK
        api_status = mp_response.get("status", 0)
        if api_status not in (200, 201):
            logging.warning(f"[PagoService] MP API error al obtener payment {payment_id}: HTTP {api_status}")
            return None

        response_body = mp_response.get("response", {})

        mp_status = response_body.get("status")
        mp_status_detail = response_body.get("status_detail")
        payment_method_id = response_body.get("payment_method_id")
        external_reference = response_body.get("external_reference")

        if not external_reference:
            logging.warning(f"[PagoService] Payment {payment_id} sin external_reference")
            return None

        pago = self.uow.pagos.get_by_external_reference(external_reference)

        pedido_id = int(external_reference)
        estado_anterior = None

        if not pago:
            # Checkout Pro flow: no Pago record exists yet, create one
            pedido = self.uow.session.get(Pedido, pedido_id)
            if not pedido:
                return None
            idempotency_key = str(uuid.uuid4())
            transaction_amount = Decimal(
                str(response_body.get("transaction_amount", pedido.monto_total))
            )
            pago = Pago(
                pedido_id=pedido_id,
                mp_payment_id=payment_id,
                mp_status=mp_status,
                mp_status_detail=mp_status_detail,
                transaction_amount=transaction_amount,
                payment_method_id=payment_method_id,
                external_reference=external_reference,
                idempotency_key=idempotency_key,
            )
            self.uow.pagos.add(pago)
            self.uow.session.flush()

            if mp_status == "approved":
                if pedido.estado == EstadoPedido.PENDIENTE:
                    estado_anterior = EstadoPedido.PENDIENTE
                    self._confirmar_pedido(pedido)

            return (pago, pedido_id, estado_anterior)

        pago.mp_payment_id = payment_id
        pago.mp_status = mp_status
        pago.mp_status_detail = mp_status_detail
        pago.payment_method_id = payment_method_id
        pago.updated_at = datetime.utcnow()
        self.uow.session.add(pago)
        self.uow.session.flush()

        if mp_status == "approved":
            pedido = self.uow.session.get(Pedido, pedido_id)
            if pedido and pedido.estado == EstadoPedido.PENDIENTE:
                estado_anterior = EstadoPedido.PENDIENTE
                self._confirmar_pedido(pedido)

        return (pago, pedido_id, estado_anterior)

    def crear_preference(
        self, pedido_id: int, usuario_id: int, user_role_codes: set[str]
    ) -> dict:
        """Crea una preferencia de Mercado Pago para Checkout Pro (redirect)."""
        pedido = self.uow.session.get(Pedido, pedido_id)
        if not pedido:
            raise ValueError("Order not found")

        if "ADMIN" not in user_role_codes and pedido.usuario_id != usuario_id:
            raise PermissionError("Order belongs to another user")

        if pedido.estado != EstadoPedido.PENDIENTE:
            raise ValueError("Order is not in PENDIENTE state")

        pago_existente = self.uow.pagos.get_by_pedido_id(pedido_id)
        if pago_existente and pago_existente.mp_status == "approved":
            raise ValueError("Order already has an approved payment")

        back_success = f"{settings.store_url}/orders/{pedido.id}?status=approved"
        back_failure = f"{settings.store_url}/orders/{pedido.id}?status=rejected"
        back_pending = f"{settings.store_url}/orders/{pedido.id}?status=pending"

        preference_payload = {
            "items": [
                {
                    "title": f"Pedido {pedido.numero_pedido}",
                    "quantity": 1,
                    "unit_price": float(pedido.monto_total),
                    "currency_id": "ARS",
                }
            ],
            "external_reference": str(pedido.id),
            "notification_url": settings.mp_notification_url,
            "back_urls": {
                "success": back_success,
                "failure": back_failure,
                "pending": back_pending,
            },
        }

        try:
            sdk = get_mp_sdk()
            mp_response = sdk.preference().create(preference_payload)
            status = mp_response.get("status", 0)
            response_body = mp_response.get("response", {})

            if status not in (200, 201):
                mp_error = response_body.get("message", response_body.get("error", str(response_body)))
                raise ValueError(f"Error de Mercado Pago (HTTP {status}): {mp_error}")

            init_point = response_body.get("init_point")
            preference_id = response_body.get("id")
            if not init_point:
                raise ValueError("Mercado Pago no devolvió un init_point en la preferencia")

            return {
                "preference_id": preference_id,
                "init_point": init_point,
            }
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Error de conexión con Mercado Pago: {str(e)}")

    def obtener_pago(self, pedido_id: int) -> Optional[Pago]:
        return self.uow.pagos.get_by_pedido_id(pedido_id)

    def _confirmar_pedido(self, pedido: Pedido) -> None:
        pedido.estado = EstadoPedido.CONFIRMADO
        pedido.updated_at = datetime.utcnow()
        historial = HistorialEstadoPedido(
            pedido_id=pedido.id,
            usuario_id=None,
            estado_anterior=EstadoPedido.PENDIENTE,
            estado_nuevo=EstadoPedido.CONFIRMADO,
            razon="Pago confirmado por MercadoPago",
        )
        self.uow.session.add(pedido)
        self.uow.session.add(historial)
        self.uow.session.flush()
    def reconciliar_pendientes(self) -> list[tuple[Pago, int, Optional[EstadoPedido]]]:
        """Consulta a MP por pagos aprobados de pedidos PENDIENTE (reconciliación activa)."""
        from sqlmodel import select
        from app.modules.pedido.models import FormaPago

        pendientes = self.uow.session.exec(
            select(Pedido).where(
                Pedido.estado == EstadoPedido.PENDIENTE,
                Pedido.forma_pago == FormaPago.MERCADO_PAGO,
            )
        ).all()
        if not pendientes:
            return []

        sdk = get_mp_sdk()
        resultados = []
        for pedido in pendientes:
            try:
                resp = sdk.payment().search({"external_reference": str(pedido.id)})
                results = resp.get("response", {}).get("results", [])
                aprobado = next((p for p in results if p.get("status") == "approved"), None)
                if not aprobado:
                    continue
                r = self.procesar_webhook({"type": "payment", "data": {"id": aprobado["id"]}})
                if r:
                    resultados.append(r)
            except Exception as e:
                logging.warning(f"[Reconciliacion] pedido {pedido.id}: {e}")
        return resultados    