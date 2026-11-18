# Publicar en Render (plan gratuito)

El proyecto se publica como **un solo servicio web** (la API de FastAPI sirve también la página) más una **base de datos PostgreSQL**. Render pone el HTTPS con un certificado administrado.
Todo está descrito en `render.yaml` y `Dockerfile.render`.

## Antes de empezar
- Una cuenta de **GitHub** y una de **Render** (se puede entrar a Render con GitHub).
- El proyecto subido a un repositorio de GitHub (los archivos `.env`, `certs/` y `node_modules/` ya están excluidos por `.gitignore`).

```bash
cd pradilla-movilidad
git init && git add . && git commit -m "Proyecto movilidad Av. Pradilla"
git branch -M main
git remote add origin https://github.com/SU-USUARIO/pradilla-movilidad.git   # cree el repositorio vacío en GitHub antes
git push -u origin main
```

## Pasos en Render
1. En Render: **New → Blueprint** y elija el repositorio. Render lee `render.yaml` y propone crear el servicio **movilidad-pradilla** y la base de datos **pradilla-db** (ambos en plan *free*).
2. Confirme con **Apply**. El primer despliegue compila la web y la API y tarda varios minutos; puede seguirlo en los *Logs*.
3. Cuando termine, abra la **URL del servicio** (aparece en el panel; termina en `.onrender.com`). El nombre exacto puede variar si ya está ocupado.
4. **Verifique:**
   - `https://SU-URL/api/health` responde `{"estado":"ok", ...}`.
   - `https://SU-URL/#info` → **Entorno de publicación**: Servidor y Hosting «Operando», Dominio, **Certificado** (tipo, emisor, vigencia, leído del dominio público) y la **versión de TLS**.
   - `curl -I http://SU-URL` debe redirigir a HTTPS.
5. Complete en `docs/RESPUESTAS_PROFESOR.md` el campo **Enlace** con esa URL.

## Mensajería (opcional pero pedida por el profesor)
Se configura en el panel del servicio → **Environment** → *Add Environment Variable*. Tras guardar, Render reinicia el servicio.

**Sincrónica — Telegram**
1. En Telegram hable con **@BotFather** → `/newbot` → guarde el **token**.
2. Cree un chat o grupo con el bot, envíe un mensaje y abra `https://api.telegram.org/bot<TOKEN>/getUpdates` para ver el `chat.id`.
3. Variables: `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.

**Asincrónica — correo (SMTP)** ⚠️ **Render bloquea en el plan gratuito los puertos SMTP 25, 465 y 587** ([aviso oficial](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports)). Opciones:
- Usar un proveedor de correo que ofrezca SMTP en el **puerto 2525** y poner `SMTP_PORT=2525` (el código usa STARTTLS en cualquier puerto distinto de 465). *No se probó con un proveedor real.*
- Pasar el servicio a un plan de pago (Render así lo sugiere).
- Si ninguna es viable, explique al profesor que el envío está implementado y probado, y que el plan gratuito lo restringe.

Variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAILS` (separados por coma). Use una *clave de aplicación*, no su contraseña personal.

La pantalla **Info** muestra qué canales están configurados (sin revelar direcciones ni tokens).

## Dominio propio (opcional)
Servicio → **Settings → Custom Domains → Add**. Cree en su proveedor de dominio el registro DNS que Render indique. Render emite y renueva el certificado solo y redirige HTTP a HTTPS; el plan gratuito incluye 2 dominios personalizados ([docs](https://render.com/docs/custom-domains)). Para un dominio gratis de estudiante vea `docs/DESPLIEGUE.md`.

## Límites del plan gratuito (importantes para la clase)
| Límite | Efecto | Qué hacer |
|---|---|---|
| **Se duerme tras 15 min sin tráfico** | La primera visita tarda ~1 min; una conexión WebSocket abierta sin mensajes no lo mantiene despierto | Abra la URL **unos minutos antes** de presentar |
| **750 horas al mes** | Si se agotan, el servicio se suspende hasta el mes siguiente | Basta para un proyecto de clase |
| **La base de datos gratis expira a los 30 días** (14 días más y se borra) | Se pierden los datos | Cree la base **cerca de la fecha de entrega**; no tiene copias de respaldo |
| **SMTP bloqueado** | Sin correo saliente (ver arriba) | Puerto 2525 o plan de pago |
| Se puede reiniciar en cualquier momento | Los clientes WebSocket se reconectan solos | Nada |

**PostGIS:** si la base gratuita no ofrece la extensión, la aplicación **arranca igual** (la geometría de los tramos también se guarda como JSON y el mapa la usa desde ahí).

## Para demostrar la validación en clase
Variable `CONFIRMACIONES_PARA_VALIDAR=1` (por defecto 2). Confirme el reporte desde **otro dispositivo o navegador**, no desde el del autor.

## Problemas frecuentes
- **El despliegue falla:** abra *Logs* del *deploy*. Revise que `render.yaml` y `Dockerfile.render` estén en la raíz del repositorio.
- **«Sin conexión en vivo»:** el servicio estaba dormido o se reinició; se reconecta solo en segundos.
- **Mapa gris:** el navegador no pudo cargar los mosaicos de OpenStreetMap; ponga una clave de MapTiler en `VITE_MAPTILER_KEY` (variable de compilación; si Render no la pasa al construir, el mapa usa OpenStreetMap).
- **Certificado «no disponible» en Info:** acaba de arrancar o no pudo consultarse; recargue en un minuto.
