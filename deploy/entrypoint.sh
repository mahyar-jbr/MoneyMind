#!/bin/sh
# MoneyMind container entrypoint.
#
# Two responsibilities:
# 1. If GOOGLE_APPLICATION_CREDENTIALS_JSON_B64 is set (Railway env var with
#    base64-encoded service-account JSON), decode it to a tmp file and point
#    GOOGLE_APPLICATION_CREDENTIALS at it. Base64 dodges shell-quoting +
#    newline-in-multiline-paste issues that broke raw JSON in env vars.
#    Falls back to GOOGLE_APPLICATION_CREDENTIALS_JSON (raw JSON) for compat.
# 2. Honor Railway's $PORT (it maps an external port to one inside the
#    container). Default to 8000 if not set (local docker run).
#
# Then: hand off to supervisord, which starts backend + agent.

set -e

if [ -n "$GOOGLE_APPLICATION_CREDENTIALS_JSON_B64" ]; then
    echo "$GOOGLE_APPLICATION_CREDENTIALS_JSON_B64" | base64 -d > /tmp/google-sa.json
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-sa.json
    echo "[entrypoint] wrote GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-sa.json (base64-decoded)"
elif [ -n "$GOOGLE_APPLICATION_CREDENTIALS_JSON" ]; then
    # Raw JSON fallback. Railway sometimes mangles multi-line values with
    # backslash-n sequences turned into literal newlines; prefer the B64 var.
    printf '%s' "$GOOGLE_APPLICATION_CREDENTIALS_JSON" > /tmp/google-sa.json
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-sa.json
    echo "[entrypoint] wrote GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-sa.json (raw, may be malformed)"
fi

if [ -n "$PORT" ]; then
    export BACKEND_PORT="$PORT"
    echo "[entrypoint] using Railway-provided PORT=$PORT for backend"
fi

# Backend reaches the agent over loopback. Explicit so it's not the default.
export AGENT_URL="http://${AGENT_HOST:-127.0.0.1}:${AGENT_PORT:-8001}"
echo "[entrypoint] AGENT_URL=$AGENT_URL (in-container loopback)"

exec supervisord -c /etc/supervisor/conf.d/moneymind.conf
