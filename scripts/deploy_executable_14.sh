#!/usr/bin/env bash
# Deploy InnerOS Executable World on Intel host (.4)
# Run ON Linux server: bash scripts/deploy_executable_14.sh
set -eu
set -o pipefail 2>/dev/null || true

SERVICE="${VOICEOPS_SERVICE:-inneros-executable-world.service}"
ENV_FILE="${EXECUTABLE_ENV_FILE:-$HOME/.config/inneros/executable.env}"
PORT="${EXECUTABLE_PORT:-8769}"
REPO_DIR="${EXECUTABLE_REPO_DIR:-$HOME/inneros/inneros_core/workspaces/inneros-executable-world-2026}"

echo "==> InnerOS Executable World deploy (.4)"
echo "    repo:    $REPO_DIR"
echo "    service: $SERVICE"
echo "    port:    $PORT"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$HOME/.config/inneros/voiceops.env" ]]; then
    cp "$HOME/.config/inneros/voiceops.env" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "==> Bootstrapped $ENV_FILE from voiceops.env"
  else
    echo "ERROR: missing $ENV_FILE" >&2
    exit 1
  fi
fi

cd "$REPO_DIR"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
chmod -R u+w src 2>/dev/null || true
.venv/bin/pip install -U pip
.venv/bin/pip install -e .

mkdir -p "$HOME/.config/systemd/user"
sed "s|%h|$HOME|g" deploy/inneros-executable-world.service.example > "$HOME/.config/systemd/user/$SERVICE"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|" "$HOME/.config/systemd/user/$SERVICE"
sed -i "s|ExecStart=.*python|ExecStart=$REPO_DIR/.venv/bin/python|" "$HOME/.config/systemd/user/$SERVICE"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE" 2>/dev/null || true
systemctl --user restart "$SERVICE"
sleep 2

curl -sf "http://127.0.0.1:${PORT}/healthz" | python3 -m json.tool
curl -sf "http://127.0.0.1:${PORT}/api/integrations/status" | python3 -m json.tool | head -40
