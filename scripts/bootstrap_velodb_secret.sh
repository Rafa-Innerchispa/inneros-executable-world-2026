#!/usr/bin/env bash
# Run interactively ON .4 — prompts for VeloDB password once, never prints it.
set -euo pipefail

CONFIG_DIR="${HOME}/.config/inneros"
WS="${HOME}/inneros/inneros_core/workspaces/inneros-executable-world-2026"
ENV_FILE="${CONFIG_DIR}/velodb.env"

mkdir -p "${CONFIG_DIR}"

if [ -f "${ENV_FILE}" ] && grep -q '^VELODB_PASSWORD=.\+' "${ENV_FILE}"; then
  echo "velodb.env already exists — reusing (delete file to re-enter password)"
else
  read -r -s -p "VeloDB password: " VELODB_PASSWORD
  echo
  if [ -z "${VELODB_PASSWORD}" ]; then
    echo "error: empty password" >&2
    exit 1
  fi
  printf 'VELODB_PASSWORD=%s\n' "${VELODB_PASSWORD}" > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  unset VELODB_PASSWORD
  echo "velodb.env written"
fi

bash "${WS}/scripts/setup_sponsor_env.sh"
systemctl --user restart inneros-executable-world.service
sleep 3

echo "--- integrations status ---"
python3 - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:8769/api/integrations/status"))
v = d["optional_adapters"]["adapters"]["velodb"]
print("velodb truth:", v.get("truth"))
print("last_probe_event_id:", v.get("last_probe_event_id"))
PY

cd "${WS}"
set -a
# shellcheck disable=SC1091
source "${HOME}/.config/inneros/executable.env"
set +a
.venv/bin/python scripts/correlated_evidence_run.py
