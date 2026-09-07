# 🍔 Food Store — Trabajo Práctico Integrador (Programación IV)

Aplicación full-stack para la gestión de un negocio de comidas: catálogo, carrito, pedidos con pago integrado vía **MercadoPago Checkout Pro**, confirmación automática por **webhook**, seguimiento en tiempo real por **WebSocket** y panel de administración con imágenes en **Cloudinary**.

**Alumno:** Rodrigo — Tecnicatura Universitaria en Programación, UTN FRM.

---

## Estructura del repositorio

```
.
├── backend/     # API REST + WebSocket (FastAPI, SQLModel, PostgreSQL, Alembic)
├── store-app/   # Tienda para clientes (React + TypeScript + Vite)
└── admin-app/   # Panel de administración (React + TypeScript + Vite)
```

Cada carpeta tiene su propio `README.md` con detalle técnico. Este archivo explica cómo levantar el sistema completo.

---

## Stack

| Capa | Tecnologías |
|---|---|
| Backend | FastAPI, SQLModel, PostgreSQL 15+, Alembic, JWT + RBAC, WebSocket, SDK MercadoPago, Cloudinary |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, Axios |
| Infra dev | ngrok (túnel público para el webhook de MercadoPago) |

---

## Requisitos previos

- Python 3.11+
- Node.js 18+ (npm o pnpm)
- PostgreSQL 15+ corriendo, con una base de datos creada (por defecto `parcial2`)
- Cuenta de desarrollador de MercadoPago (para las credenciales de prueba)
- Cuenta de Cloudinary (para subir imágenes desde el admin)
- ngrok (solo para probar el webhook de MercadoPago)

---

## 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### Variables de entorno

Copiá `.env.example` a `.env` y completá:

```env
DATABASE_URL=postgresql+psycopg://postgres:TU_PASSWORD@localhost:5432/parcial2
SECRET_KEY=una-clave-larga-y-secreta-de-al-menos-32-caracteres
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# MercadoPago (credenciales de PRUEBA — ver sección "MercadoPago" más abajo)
MP_ACCESS_TOKEN=APP_USR-...
MP_PUBLIC_KEY=APP_USR-...
MP_NOTIFICATION_URL=https://TU-DOMINIO.ngrok-free.dev/api/v1/pagos/webhook
STORE_URL=http://localhost:5173

# Cloudinary
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

### Migraciones y arranque

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Al iniciar, el backend ejecuta el **seed** automáticamente (roles, estados de pedido, formas de pago, unidades de medida y usuario admin).

- Swagger: http://localhost:8000/docs
- Usuario admin por defecto: `admin@example.com` / `admin123`

> `--host 0.0.0.0` es necesario para que ngrok (si corre en WSL) pueda alcanzar el backend.

---

## 2. Store (tienda)

```powershell
cd store-app
npm install
npm run dev
```

Corre en http://localhost:5173

## 3. Admin (panel)

```powershell
cd admin-app
npm install
npm run dev
```

Corre en http://localhost:5174

---

## 4. MercadoPago — configuración de prueba

El flujo usa **cuentas de prueba** de MercadoPago, que es el mecanismo actual de sandbox:

1. En [mercadopago.com.ar/developers](https://www.mercadopago.com.ar/developers) → Tus integraciones → crear una aplicación (Pagos online, Checkout Pro).
2. En esa app → **Cuentas de prueba** → crear una de tipo **Vendedor** y otra de tipo **Comprador** (con saldo), ambas de Argentina.
3. En una ventana de incógnito, iniciar sesión en MercadoPago con el usuario **Vendedor** de prueba y crear otra aplicación desde esa cuenta.
4. Copiar las **Credenciales de producción** de esa app (empiezan con `APP_USR-`). Al pertenecer a una cuenta de prueba, solo mueven dinero ficticio. Esas son las que van en `MP_ACCESS_TOKEN` y `MP_PUBLIC_KEY`.
5. El usuario **Comprador** de prueba se usa para iniciar sesión en el checkout al momento de pagar.

### Túnel público para el webhook

MercadoPago necesita una URL pública para notificar los pagos:

```bash
ngrok http --domain=TU-DOMINIO.ngrok-free.dev localhost:8000
```

Si ngrok corre en **WSL** y el backend en **Windows**, reemplazá `localhost` por la IP del host (`ip route show | grep default | awk '{print $3}'`) y, si hace falta, abrí el puerto en el firewall de Windows:

```powershell
New-NetFirewallRule -DisplayName "uvicorn 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

La URL resultante va en `MP_NOTIFICATION_URL` (reiniciar el backend después de cambiarla). Las requests entrantes se pueden inspeccionar en http://localhost:4040.

---

## 5. Flujo de demostración (pago end-to-end)

1. Levantar backend, store, admin y ngrok (en ese orden).
2. En el store, registrarse o iniciar sesión, agregar productos al carrito y crear el pedido con forma de pago **Mercado Pago**.
3. En el checkout de MercadoPago, iniciar sesión con el usuario **Comprador** de prueba y pagar (con dinero en cuenta, o con tarjeta de prueba `4509 9535 6623 3704`, CVV `123`, vencimiento `11/30`, nombre `APRO`).
4. MercadoPago envía el webhook (`type=payment`) al backend, que:
   - consulta el pago en la API de MP,
   - lo registra en la tabla `pago` (`mp_status = approved`),
   - avanza el pedido de **PENDIENTE → CONFIRMADO** con la entrada "Pago confirmado por MercadoPago" en el historial,
   - emite el evento `pago_confirmado` por WebSocket.
5. En el admin (Pedidos) el pedido aparece en **Confirmados** sin intervención manual, y desde ahí se puede avanzar por la FSM (En preparación → Entregado) arrastrando la tarjeta.

---

## Máquina de estados del pedido

```
PENDIENTE ──(pago aprobado / webhook)──▶ CONFIRMADO ──▶ EN_PREPARACION ──▶ ENTREGADO
    │                                        │                  │
    └────────────────────── CANCELADO ◀──────┴──────────────────┘
```

`ENTREGADO` y `CANCELADO` son estados terminales. Todas las transiciones quedan registradas en `historial_estado_pedido` (append-only).

---

## Tests

```powershell
cd backend
pytest
```