#!/usr/bin/env bash
# Obtiene el certificado gratuito de Let's Encrypt (validación de dominio, 90 días) y activa la renovación.
# Requisitos: el dominio ya apunta (registro A) a la IP pública de este servidor y los puertos 80 y 443 están abiertos.
# Uso:  ./scripts/init-letsencrypt.sh           (certificado real)
#       STAGING=1 ./scripts/init-letsencrypt.sh (prueba sin gastar el límite de Let's Encrypt)
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "Falta .env (copie .env.example y complételo)"; exit 1; }
set -a; . ./.env; set +a
: "${DOMAIN:?Defina DOMAIN en .env (ej. movilidad.midominio.co)}"
: "${LETSENCRYPT_EMAIL:?Defina LETSENCRYPT_EMAIL en .env}"

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
export SSL_CERT_PATH="${CERT_DIR}/fullchain.pem"
export SSL_KEY_PATH="${CERT_DIR}/privkey.pem"
COMPOSE="docker compose --profile produccion"

echo "1/5 Creando un certificado temporal para que nginx pueda arrancar..."
$COMPOSE run --rm --entrypoint "sh -c 'mkdir -p ${CERT_DIR} && openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout ${SSL_KEY_PATH} -out ${SSL_CERT_PATH} -subj /CN=localhost'" certbot

echo "2/5 Iniciando nginx..."
$COMPOSE up -d --build web

echo "3/5 Quitando el certificado temporal..."
$COMPOSE run --rm --entrypoint "sh -c 'rm -rf /etc/letsencrypt/live/${DOMAIN} /etc/letsencrypt/archive/${DOMAIN} /etc/letsencrypt/renewal/${DOMAIN}.conf'" certbot

echo "4/5 Solicitando el certificado a Let's Encrypt para ${DOMAIN}..."
STAGING_ARG=""; [ "${STAGING:-0}" = "1" ] && STAGING_ARG="--staging"
EXTRA_DOMAINS=""; [ -n "${WWW_DOMAIN:-}" ] && EXTRA_DOMAINS="-d ${WWW_DOMAIN}"
$COMPOSE run --rm --entrypoint "certbot certonly --webroot -w /var/www/certbot \
  -d ${DOMAIN} ${EXTRA_DOMAINS} --email ${LETSENCRYPT_EMAIL} --agree-tos --no-eff-email --rsa-key-size 2048 ${STAGING_ARG} --force-renewal" certbot

echo "5/5 Recargando nginx y levantando todo (incluida la renovación automática)..."
$COMPOSE up -d
$COMPOSE exec web nginx -s reload

echo
echo "Listo. Abra https://${DOMAIN}  y revise la pantalla Info → «Entorno de publicación»."
[ "${STAGING:-0}" = "1" ] && echo "AVISO: usó STAGING; el certificado NO es de confianza. Repita sin STAGING=1 para el real."
