# Respuestas para el profesor — Proyecto Movilidad Av. Pradilla (Chía)

**Equipo:** Juan Miguel Espejo Bueno · Tomás Felipe Niño Roa · Elkin Leandro Arevalo Martinez
**Problemática:** en las tardes la Avenida Pradilla se congestiona y un trancón puede durar mucho en un trayecto corto. El proyecto muestra las horas pico, rutas alternativas y transporte, y recomienda a qué hora salir mediante un Índice de Presión Vial (IPV).

**Enlace del proyecto:** `COMPLETAR: https://____.onrender.com`  *(se obtiene al publicar; ver `docs/DESPLIEGUE_RENDER.md`)*

> Los campos `COMPLETAR` dependen de publicar el servicio. Todo lo demás está implementado y probado en el código entregado.

---

## 1. ¿En qué servidor está?

Siguiendo el esquema de clase (**Entorno web → Servidor = Hosting + Dominio**):

| Elemento | Valor |
|---|---|
| **Hosting** | **Render** (PaaS), plan gratuito, región Virginia (EE. UU.) |
| **Dominio** | `COMPLETAR: ____.onrender.com` (dominio que entrega Render; se puede asociar uno propio) |
| **Servidor de aplicación** | Uvicorn + FastAPI (Python) en un contenedor Docker, detrás del proxy de Render |
| **Base de datos** | PostgreSQL administrado por Render (PostGIS cuando el plan lo ofrece) |

La aplicación **demuestra** que el servidor y el dominio operan: *Info → Entorno de publicación* (`/#info`) muestra el estado en vivo de servidor, hosting, dominio, certificado, conexión segura y mensajería, leído del propio servidor.

## 2. ¿Qué arquitectura usa?

**Cliente-servidor en 3 capas, con API REST más un canal en tiempo real, en un servicio en la nube (PaaS).**

```
 Celular / PC (PWA React)
        │  HTTPS (TLS)  +  WSS (WebSocket cifrado)
        ▼
 Proxy / balanceador de Render  ← termina TLS, certificado administrado, HTTP → HTTPS
        │  red interna de Render
        ▼
 Contenedor único (Docker)
 ┌───────────────────────────────────────────┐
 │ FastAPI: API REST + WebSocket + web estática │
 └───────────┬───────────────────────────────┘
             │ conexión interna (la base no es accesible desde Internet)
             ▼
      PostgreSQL (Render)
   salidas ► API de Telegram (HTTPS) · correo (SMTP)
 GitHub: código · GitHub Actions: pruebas · Render: construye y despliega la imagen
```

| Capa | Tecnología | Función |
|---|---|---|
| Presentación | React + Vite (PWA), Recharts, Leaflet + OpenStreetMap | Pantallas «mobile first», gráficos de horas pico, mapa |
| Lógica | FastAPI (Python) | IPV, pronóstico, planificador «¿A qué hora salgo?», reportes, mensajería |
| Datos | PostgreSQL | Histórico por tramo, día y hora; rutas; transporte; reportes |
| Borde | Proxy de Render | TLS, certificado, redirección a HTTPS |

**Por qué:** separa presentación, lógica y datos; un solo servicio con la web y la API en el mismo origen simplifica la seguridad (sin CORS) y el WebSocket; la base de datos no se expone a Internet; y todo se describe en archivos (`render.yaml`, `Dockerfile.render`), por lo que es reproducible.

## 3. ¿Cómo se aplica el cifrado TLS?

**Qué es:** TLS cifra la comunicación entre el navegador y el servidor (HTTP pasa a HTTPS) para dar **confidencialidad**, **integridad** y **autenticación del servidor** mediante un certificado.

**Cómo se aplica en el proyecto:**
- **Render termina TLS** en su proxy con un **certificado administrado** que emite y renueva automáticamente (Let's Encrypt o Google Trust Services, según su documentación) y redirige HTTP a HTTPS.
- La aplicación agrega **HSTS** (1 año, `includeSubDomains`), **Content-Security-Policy** y demás cabeceras de seguridad, y oculta la versión del servidor.
- El WebSocket viaja cifrado como **WSS**; Telegram usa HTTPS; el correo usa **SMTP con STARTTLS**.

**Certificado (tipos vistos en clase):**

| Tipo | Qué valida | Duración típica | ¿Cuál se usa? |
|---|---|---|---|
| **Dominio (DV)** | Que se controla el dominio | ≈ 3 meses (90 días) | **Sí**: lo emite y renueva Render sin costo |
| Organizacional (OV) | Dominio + existencia de la organización | ≈ 1 año | No (se compra; la web lo reconoce y lo muestra) |
| Extendido (EV) | Verificación legal estricta | ≈ 1 año | No (se compra; la web lo reconoce y lo muestra) |

**Cómo funciona la conexión:** (1) el navegador propone versiones y suites; (2) el servidor responde con su certificado; (3) el navegador verifica cadena, dominio y vigencia; (4) acuerdan una clave de sesión con intercambio de claves efímero; (5) el tráfico viaja cifrado.

**Alcance (con honestidad):**
- El certificado y los parámetros de TLS **los administra Render; no los configuramos manualmente**. Lo que sí configuramos: la redirección/HSTS desde la aplicación, la política de seguridad y el uso de WSS.
- El cifrado protege navegador ↔ proxy de Render. El tramo interno hasta el contenedor lo gestiona Render.
- Los datos guardados en la base no están cifrados por la aplicación.

**Evidencia:** *Info → Entorno de publicación* abre una conexión TLS real al dominio público y muestra **tipo, emisor, vigencia, días restantes, huella, versión de TLS y cifrado** (la cadena de confianza se verifica; si no es válida, no se muestra como válida). Verificación externa: `curl -I http://dominio` (redirección) y `curl -I https://dominio` (cabecera `strict-transport-security`).

## 4. Mensajería sincrónica y asincrónica

**Definición:** *sincrónica* = emisor y receptor interactúan al mismo tiempo y la respuesta es inmediata. *Asincrónica* = el mensaje queda almacenado y se lee después, sin conexión simultánea.

| Tipo | Opción vista en clase | ¿Implementada? | Cómo |
|---|---|---|---|
| **Sincrónica** | **Web (JavaScript)** | ✅ Sí | **WebSocket** (`/api/ws`, `wss://`). La web recibe al instante reportes nuevos, confirmados y validados; muestra «● En vivo» y actualiza el índice |
| **Sincrónica** | **Integración móvil (Telegram/WhatsApp)** | ✅ Telegram · ❌ WhatsApp | Bot de **Telegram** (HTTPS) avisa al chat del equipo cuando la comunidad valida un reporte. Requiere token. WhatsApp no se implementó |
| **Sincrónica** | **XMPP** | ❌ No | Protocolo abierto de mensajería instantánea; WebSocket cubre el tiempo real |
| **Asincrónica** | **Correo (POP3 / IMAP)** | ✅ Envío SMTP · lectura por IMAP/POP3 | La API **envía** por SMTP + STARTTLS **en segundo plano**. El equipo **lee** con IMAP (conserva los correos en el servidor y sincroniza varios dispositivos) o POP3 (los descarga a un solo equipo) |

> ⚠️ **En el plan gratuito de Render el correo saliente está restringido** (bloquea los puertos SMTP 25, 465 y 587). El envío está implementado y probado con un servidor SMTP simulado; en Render gratuito requiere un proveedor con puerto 2525 o un plan de pago (ver `docs/DESPLIEGUE_RENDER.md`).

**Flujo de ejemplo:**
1. Una persona reporta un accidente → el servidor lo difunde **por WebSocket** a todos los conectados *(sincrónica)*.
2. Otras personas lo confirman; al alcanzar las confirmaciones necesarias queda **validado** y el IPV del tramo se ajusta en vivo *(sincrónica)*.
3. Se avisa por **Telegram** *(sincrónica móvil)* y se envía un **correo** que el equipo leerá después *(asincrónica)*.

**Seguridad de la mensajería:** verificación del origen del WebSocket (solo el mismo sitio), límite de 200 conexiones y de tamaño de mensaje, eventos sin datos personales ni texto libre, credenciales solo en variables de entorno (nunca en el código ni en los registros), protección contra inyección de cabeceras de correo, y un fallo de mensajería nunca rompe el reporte.

## Cómo demostrarlo en clase
1. **Abra la URL unos minutos antes** (el plan gratuito se duerme tras 15 min sin tráfico y tarda ~1 min en despertar).
2. `https://dominio/#info` → Servidor y Hosting «Operando», certificado «Vigente» (tipo Dominio), TLS, mensajería.
3. `/#reportar` en **dos dispositivos**: al enviar un reporte en uno, aparece **al instante** en el otro *(sincrónica)*.
4. Para validar rápido: variable `CONFIRMACIONES_PARA_VALIDAR=1` y confirmar desde otro dispositivo o navegador.
5. Mostrar el aviso en **Telegram** (y el correo si se logró configurar SMTP).

## Pruebas realizadas
- 56 pruebas automáticas del servidor (IPV, planificador, reportes, certificados —incluida una conexión TLS real con verificación de cadena—, WebSocket, Telegram, correo, seguridad) y 3 del front-end; compilación de producción correcta.
- Simulación del servicio único (web + API en un solo proceso): sin violaciones de la política de seguridad en el navegador y WebSocket «En vivo».
- Con un servidor real, un cliente WebSocket recibió `reporte_nuevo → reporte_confirmado → reporte_validado` y se rechazó un origen ajeno.

## Pendiente por el equipo
- **Publicar en Render** y completar el **enlace** (guía: `docs/DESPLIEGUE_RENDER.md`).
- Configurar el token de Telegram (y SMTP si se desea mostrar el correo).
- Las **mediciones reales de tráfico** (el histórico actual es de demostración) y las pruebas en dispositivos.
- La imagen Docker y el *blueprint* no se pudieron construir ni desplegar en el entorno de desarrollo (sin Docker ni cuenta de Render); se validaron por partes.
