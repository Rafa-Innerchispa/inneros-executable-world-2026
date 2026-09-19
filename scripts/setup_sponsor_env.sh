#!/usr/bin/env bash
# Configure sponsor env on .4 — never prints secrets.
set -euo pipefail

ENV="${HOME}/.config/inneros/executable.env"
mkdir -p "$(dirname "$ENV")"
touch "$ENV"

upsert() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV"
  else
    echo "${key}=${val}" >> "$ENV"
  fi
}

upsert EXECUTABLE_ENABLE_EDGEONE true
upsert EDGEONE_PAGES_PROJECT inneros-executable-world-2026
upsert EDGEONE_WITNESS_URL http://127.0.0.1:8791/
upsert EXECUTABLE_ENABLE_AGENTX true
upsert AGENTX_SELF_HOSTED_URL http://127.0.0.1:4700
upsert EXECUTABLE_ENABLE_VELODB true
upsert VELODB_HOST lb-19722502-64fe987bf0d59678.elb.us-west-1.amazonaws.com
upsert VELODB_PORT 9030
upsert VELODB_USER admin
upsert VELODB_DATABASE inneros_executable_world

if [ -f "${HOME}/.config/inneros/agentx.env" ]; then
  # shellcheck disable=SC1091
  source "${HOME}/.config/inneros/agentx.env"
fi
if [ -f "${HOME}/.config/inneros/velodb.env" ]; then
  # shellcheck disable=SC1091
  source "${HOME}/.config/inneros/velodb.env"
fi
if [ -n "${VELODB_PASSWORD:-}" ]; then
  upsert VELODB_PASSWORD "${VELODB_PASSWORD}"
fi
if [ -n "${AGENTX_API_KEY:-}" ]; then
  upsert AGENTX_API_KEY "${AGENTX_API_KEY}"
fi

echo "sponsor_env_updated"
grep -E '^(EXECUTABLE_ENABLE|EDGEONE_PAGES|EDGEONE_WITNESS|AGENTX_SELF|VELODB_HOST|VELODB_PORT|VELODB_USER|VELODB_DATABASE|AGENTX_API_KEY)=' "$ENV" \
  | sed 's/AGENTX_API_KEY=.*/AGENTX_API_KEY=***/' \
  | sed 's/VELODB_PASSWORD=.*/VELODB_PASSWORD=***/'
