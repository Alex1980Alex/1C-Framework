#!/bin/bash
# Generate self-signed SSL certificates for development
# Usage: ./generate.sh [domain]

DOMAIN="${1:-localhost}"
DAYS=365
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Generating self-signed SSL certificate for: ${DOMAIN}"

openssl req -x509 -nodes -days "${DAYS}" \
    -newkey rsa:2048 \
    -keyout "${DIR}/key.pem" \
    -out "${DIR}/cert.pem" \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=PDF-Framework/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},IP:127.0.0.1"

echo "Certificate generated:"
echo "  cert: ${DIR}/cert.pem"
echo "  key:  ${DIR}/key.pem"
echo "  valid: ${DAYS} days"
