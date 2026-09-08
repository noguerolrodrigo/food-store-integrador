import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.core.database import engine
from app.db.seed import seed_database

from app.modules.categoria.router import router as categoria_router
from app.modules.ingrediente.router import router as ingrediente_router
from app.modules.producto.router import router as producto_router
from app.modules.producto_categoria.router import router as producto_categoria_router
from app.modules.producto_ingrediente.router import router as producto_ingrediente_router
from app.modules.usuario.router import router as usuario_router
from app.modules.pedido.router import router as pedido_router
from app.modules.pedido.ws_router import ws_router
from app.modules.pagos.router import router as pagos_router
from app.modules.direccion.router import router as direccion_router
from app.modules.auth.router import router as auth_router
from app.modules.unidad_medida.router import router as unidad_medida_router
from app.modules.estadisticas.router import router as estadisticas_router
from app.modules.uploads.router import router as uploads_router

from app.modules.categoria.model import Categoria  # noqa: F401
from app.modules.ingrediente.model import Ingrediente  # noqa: F401
from app.modules.producto.model import Producto  # noqa: F401
from app.modules.producto_categoria.model import ProductoCategoria  # noqa: F401
from app.modules.producto_ingrediente.model import ProductoIngrediente  # noqa: F401
from app.modules.usuario.models import Usuario, Rol, UsuarioRol  # noqa: F401
from app.modules.pedido.models import Pedido, DetallePedido, HistorialEstadoPedido  # noqa: F401
from app.modules.pagos.model import Pago  # noqa: F401
from app.modules.direccion.models import DireccionEntrega  # noqa: F401
from app.modules.unidad_medida.model import UnidadMedida  # noqa: F401
from app.modules.auth.model import RefreshToken  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.modules.pagos.router import reconciliar_pagos_loop

    with Session(engine) as session:
        seed_database(session)
        session.commit()

    tarea = asyncio.create_task(reconciliar_pagos_loop())
    yield
    tarea.cancel()

app = FastAPI(
    title="API Parcial FastAPI + SQLModel",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTPException %s: %s %s", exc.status_code, request.method, request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s %s - %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos para imágenes subidas
media_dir = Path(__file__).resolve().parent.parent / "media"
media_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

app.include_router(auth_router)
app.include_router(categoria_router)
app.include_router(ingrediente_router)
app.include_router(producto_router)
app.include_router(producto_categoria_router)
app.include_router(producto_ingrediente_router)
app.include_router(usuario_router)
app.include_router(pedido_router)
app.include_router(ws_router)
app.include_router(pagos_router)
app.include_router(direccion_router)
app.include_router(unidad_medida_router)
app.include_router(estadisticas_router)
app.include_router(uploads_router)


@app.get("/")
def healthcheck():
    return {"message": "Backend activo"}
