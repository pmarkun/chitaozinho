#!/bin/sh
set -eu

readonly listen_port="${PORT:-8080}"
readonly health_url="https://127.0.0.1:8200/v1/sys/health"

if [ "${OPENBAO_READINESS_RESPONSE:-}" = "1" ]; then
  if wget --quiet --no-check-certificate --output-document=/dev/null "$health_url"; then
    status="200 OK"
    body="ready"
  else
    status="503 Service Unavailable"
    body="sealed"
  fi

  body_length=${#body}
  {
    printf 'HTTP/1.1 %s\r\n' "$status"
    printf 'Content-Type: text/plain; charset=utf-8\r\n'
    printf 'Content-Length: %s\r\n' "$body_length"
    printf 'Cache-Control: no-store\r\n'
    printf 'Connection: close\r\n\r\n'
    printf '%s' "$body"
  }
  exit 0
fi

export OPENBAO_READINESS_RESPONSE=1
exec nc -lk -p "$listen_port" -e "$0"
