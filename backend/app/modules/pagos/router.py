import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.core.deps import get_current_user, require_role
from app.core.ws_manager import ws_manager
from app.modules.pagos.pagos_uow import PagoUnitOfWork
from app.modules.pagos.schema import (
    PagoCreate,
    PagoRead,
    PreferenceCreateRequest,
    PreferenceCreateResponse,
)
from app.modules.pagos.service import PagoService, get_mp_sdk
from app.modules.usuario.models import Usuario

router = APIRouter(prefix="/api/v1/pagos", tags=["Pagos"])


@router.post("/crear", response_model=PagoRead, status_code=status.HTTP_201_CREATED)
async def crear_pago(
    data: PagoCreate,
    current_user: Usuario = Depends(require_role(["CLIENT", "ADMIN"])),
):
    try:
        with PagoUnitOfWork() as uow:
            service = PagoService(uow)
            pago = service.crear_pago(data, current_user.id)
            pid = pago.pedido_id
            mp_status = pago.mp_status
            owner_id = pago.pedido.usuario_id
            response = PagoRead.model_validate(pago)

        # RN-06: broadcast DESPUÉS del commit del UoW
        if mp_status == "approved":
            await ws_manager.broadcast_pedido(pid, owner_id, {
                "event": "pago_confirmado",
                "pedido_id": pid,
                "estado_anterior": "PENDIENTE",
                "estado_nuevo": "CONFIRMADO",
                "usuario_id": current_user.id,
                "motivo": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })

        return response

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/create-preference",
    response_model=PreferenceCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_preference(
    data: PreferenceCreateRequest,
    current_user: Usuario = Depends(require_role(["CLIENT", "ADMIN"])),
):
    try:
        with PagoUnitOfWork() as uow:
            service = PagoService(uow)
            user_role_codes = {r.codigo for r in current_user.roles}
            result = service.crear_preference(
                data.pedido_id, current_user.id, user_role_codes
            )
        return PreferenceCreateResponse(
            **result, pedido_id=data.pedido_id
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except ValueError as e:
        detail = str(e)
        status_code_val = status.HTTP_400_BAD_REQUEST
        if detail == "Order not found":
            status_code_val = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code_val, detail=detail)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook_post(request: Request):
    return await _procesar_notificacion_mp(request)


@router.get("/webhook", status_code=status.HTTP_200_OK)
async def webhook_get(request: Request):
    return await _procesar_notificacion_mp(request)


async def _procesar_notificacion_mp(request: Request) -> dict:
    """Procesa notificaciones de Mercado Pago (POST con JSON o GET/POST con query params)"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    # IPN / query params format: ?topic=payment&id=12345
    topic = request.query_params.get("topic")
    query_id = request.query_params.get("id")
    if topic and query_id:
        body["type"] = topic
        body["data"] = {"id": int(query_id)}

    notification_type = body.get("type")
    if not notification_type:
        return {"status": "ok"}

    logging.info(f"[Webhook MP] type={notification_type}, body={body}")

    if notification_type == "merchant_order":
        try:
            merchant_order_id = int(body["data"]["id"])
            sdk = get_mp_sdk()
            mo_response = sdk.merchant_order().get(merchant_order_id)
            mo_body = mo_response.get("response", {})

            # Verificar estado del merchant_order
            mo_status = mo_response.get("status", 0)
            if mo_status not in (200, 201):
                logging.warning(f"[Webhook MP] merchant_order API error: HTTP {mo_status}")
                return {"status": "ok"}

            payments = mo_body.get("payments", [])
            if not payments:
                logging.warning(f"[Webhook MP] merchant_order {merchant_order_id} sin payments")
                return {"status": "ok"}

            payment_id = payments[0]["id"]
            body["type"] = "payment"
            body["data"] = {"id": payment_id}
            logging.info(f"[Webhook MP] merchant_order -> payment_id={payment_id}")
        except Exception as e:
            logging.error(f"[Webhook MP] Error procesando merchant_order: {e}", exc_info=True)
            return {"status": "ok"}

    result = None
    mp_status = None
    owner_id = None

    try:
        with PagoUnitOfWork() as uow:
            service = PagoService(uow)
            result = service.procesar_webhook(body)
            if result:
                pago, pedido_id, estado_anterior = result
                mp_status = pago.mp_status
                owner_id = pago.pedido.usuario_id

        # RN-06: broadcast DESPUÉS del commit del UoW
        if result and mp_status == "approved":
            _, pedido_id, estado_anterior = result
            await ws_manager.broadcast_pedido(pedido_id, owner_id, {
                "event": "pago_confirmado",
                "pedido_id": pedido_id,
                "estado_anterior": estado_anterior.value if estado_anterior else None,
                "estado_nuevo": "CONFIRMADO",
                "usuario_id": None,
                "motivo": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
    except Exception as e:
        logging.error(f"[Webhook MP] Error inesperado: {e}", exc_info=True)

    return {"status": "ok"}


@router.get("/{pedido_id}", response_model=PagoRead)
def obtener_pago(
    pedido_id: Annotated[int, Path(gt=0)],
    current_user: Usuario = Depends(get_current_user),
):
    with PagoUnitOfWork() as uow:
        service = PagoService(uow)
        pago = service.obtener_pago(pedido_id)

        if not pago:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pago no encontrado para este pedido",
            )

        user_roles = {r.codigo for r in current_user.roles}
        if "ADMIN" not in user_roles and pago.pedido.usuario_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sin permisos para ver este pago",
            )

        return PagoRead.model_validate(pago)
async def reconciliar_pagos_loop(intervalo: int = 10):
    """Tarea de fondo: cada N segundos busca en MP pagos aprobados de pedidos pendientes."""
    import asyncio
    while True:
        await asyncio.sleep(intervalo)
        try:
            confirmados = []
            with PagoUnitOfWork() as uow:
                for pago, pedido_id, estado_anterior in PagoService(uow).reconciliar_pendientes():
                    if estado_anterior is not None:
                        confirmados.append((pedido_id, pago.pedido.usuario_id, estado_anterior))
            for pedido_id, owner_id, estado_anterior in confirmados:
                logging.info(f"[Reconciliacion] pedido {pedido_id} confirmado desde MP")
                await ws_manager.broadcast_pedido(pedido_id, owner_id, {
                    "event": "pago_confirmado",
                    "pedido_id": pedido_id,
                    "estado_anterior": estado_anterior.value,
                    "estado_nuevo": "CONFIRMADO",
                    "usuario_id": None,
                    "motivo": None,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
        except Exception as e:
            logging.error(f"[Reconciliacion] Error: {e}", exc_info=True)