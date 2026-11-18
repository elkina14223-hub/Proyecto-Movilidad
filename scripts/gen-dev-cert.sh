#!/usr/bin/env bash
# Genera un certificado AUTOFIRMADO solo para desarrollo local (https://localhost:8443).
# En producción use un certificado de una CA reconocida (p. ej. Let's Encrypt con certbot)
# y copie fullchain.pem y privkey.pem en ./certs.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p certs
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout certs/privkey.pem -out certs/fullchain.pem \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
echo "Certificado de desarrollo creado en ./certs"
