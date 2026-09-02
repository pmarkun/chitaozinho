#!/bin/sh
set -eu

: "${OPENBAO_TLS_CERT_PEM:?OPENBAO_TLS_CERT_PEM is required}"
: "${OPENBAO_TLS_KEY_PEM:?OPENBAO_TLS_KEY_PEM is required}"

umask 077
mkdir -p /openbao/config /openbao/data/raft
printf '%s\n' "$OPENBAO_TLS_CERT_PEM" > /openbao/config/tls.crt
printf '%s\n' "$OPENBAO_TLS_KEY_PEM" > /openbao/config/tls.key
if [ "$(id -u)" = 0 ]; then
  chown -R openbao:openbao /openbao/config /openbao/data
fi

cat > /openbao/config/railway.json <<'EOF'
{
  "api_addr": "https://openbao.railway.internal:8200",
  "cluster_addr": "https://openbao.railway.internal:8201",
  "disable_mlock": true,
  "ui": false,
  "listener": {
    "tcp": {
      "address": "[::]:8200",
      "cluster_address": "[::]:8201",
      "tls_cert_file": "/openbao/config/tls.crt",
      "tls_key_file": "/openbao/config/tls.key",
      "tls_min_version": "tls13"
    }
  },
  "storage": {
    "raft": {
      "path": "/openbao/data/raft",
      "node_id": "openbao-railway-beta"
    }
  },
  "audit": [
    {
      "file": {
        "stdout": {
        "description": "Railway log stream",
        "options": {"file_path": "stdout"}
        }
      }
    }
  ]
}
EOF
if [ "$(id -u)" = 0 ]; then
  chown openbao:openbao /openbao/config/railway.json
  exec su-exec openbao bao server -config=/openbao/config
fi
exec bao server -config=/openbao/config
