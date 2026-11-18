# Guía de despliegue: servidor, hosting, dominio y certificado

Esta guía sigue el esquema del tablero: **Entorno web → Servidor (Hosting operando, Dominio operando) → Configuración de certificados**.

## Qué necesita (lo consigue usted, yo no puedo contratarlo)

| Pieza | Qué es | Opciones |
|---|---|---|
| **Hosting** | Un servidor Linux con IP pública y Docker (un VPS pequeño basta: 1 vCPU, 2 GB RAM). | Cualquier proveedor de VPS. Para KAN-30 conviene uno con centro de datos en Colombia o cercano, o poner un CDN delante. |
| **Dominio** | Un nombre (ej. `movilidad.midominio.co`) con registro **A** apuntando a la IP del VPS. | Comprar uno en un registrador, o un subdominio gratuito (DuckDNS, etc.) para pruebas. |
| **Certificado** | El candado HTTPS. Ver tipos abajo. | Let's Encrypt (gratis, automático). |

### Tipos de certificado (según el tablero)

| Tipo | Valida | Duración típica | ¿Lo automatiza este proyecto? |
|---|---|---|---|
| **Dominio (DV)** | Que usted controla el dominio | ≈ 3 meses (Let's Encrypt: 90 días) | **Sí**, gratis, con renovación automática |
| **Organizacional (OV)** | Dominio + que la organización existe | ≈ 1 año | No: se compra a una CA y se copia a `certs/` |
| **Extendido (EV)** | Verificación legal estricta de la organización | ≈ 1 año | No: se compra a una CA y se copia a `certs/` |

> Interpreté «Certificados (Lifindo)» como el certificado gratuito de dominio de 3 meses. Si se refería a otro, avíseme y lo ajusto.

La web **detecta y muestra el tipo real** del certificado instalado (Info → Entorno de publicación).

## Pasos (certificado gratuito Let's Encrypt)

1. **VPS:** instale Docker y Docker Compose; abra los puertos 80 y 443.
2. **Dominio:** cree el registro A hacia la IP del VPS y espere a que propague (`nslookup su-dominio`).
3. **Código:** copie el proyecto al VPS (por ejemplo en `/opt/pradilla-movilidad`).
4. **Configuración:** `cp .env.example .env` y complete lo marcado como PRODUCCIÓN:
   `DOMAIN`, `LETSENCRYPT_EMAIL`, `HTTP_PORT=80`, `HTTPS_PORT=443`, `PUBLIC_HTTPS_SUFFIX=` (vacío),
   `CORS_ORIGINS`, `SSL_CERT_PATH`, `SSL_KEY_PATH`, y los datos del hosting (`HOSTING_PROVIDER`, `HOSTING_REGION`, `HOSTING_TYPE`).
   Cambie también `POSTGRES_PASSWORD` y `REPORT_SALT`.
5. **Prueba sin riesgo:** `STAGING=1 ./scripts/init-letsencrypt.sh` (certificado de prueba, no confiable).
6. **Real:** `./scripts/init-letsencrypt.sh`
7. **Verifique:** abra `https://su-dominio/#info`. Debe ver Servidor, Hosting y Dominio «Operando», Certificado «Vigente» con tipo «Validación de dominio (DV)», y HTTPS activo con TLS 1.3.

El contenedor `certbot` renueva solo (revisa cada 12 h) y nginx recarga el certificado cada 6 h.

## Comprobaciones externas recomendadas
- `curl -I http://su-dominio` → debe responder **301** hacia https.
- `curl -I https://su-dominio` → debe incluir `strict-transport-security`.
- Un analizador TLS público (por ejemplo SSL Labs) para confirmar TLS 1.3/1.2 y la cadena completa.

## Problemas frecuentes
- *Let's Encrypt falla con «connection refused/timeout»:* el dominio no apunta aún al VPS o el puerto 80 está cerrado.
- *«Too many requests»:* use `STAGING=1` mientras prueba.
- *La web muestra «Solo local» en Dominio:* está entrando por IP o `localhost`; entre por el dominio.
- *Certificado «No confiable (autofirmado)»:* se está usando el de desarrollo (`gen-dev-cert.sh`).
