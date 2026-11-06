#!/usr/bin/env sh
# Vault Heist for macOS and Linux. Sets everything up on the first run, then starts the game.
#   ./play.sh            play
#   ./play.sh --all      also install Langfuse, NeMo Guardrails, and CrewAI
#   ./play.sh doctor     any other argument goes to the vault-heist command
set -e
cd "$(dirname "$0")"

EXTRAS=""
if [ "${1:-}" = "--all" ]; then EXTRAS="--all-extras"; shift; fi

echo ""
echo " ===== Vault Heist setup ====="
if ! command -v uv >/dev/null 2>&1; then
  if [ -x "$HOME/.local/bin/uv" ]; then
    PATH="$HOME/.local/bin:$PATH"
  else
    echo " [1/3] Installing uv, the Python toolchain manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
  fi
fi
export PATH

echo " [2/3] Installing Python and packages. The first run takes a minute or two..."
uv sync $EXTRAS

[ -f .env ] || cp .env.example .env
echo " [3/3] Ready."

if [ $# -eq 0 ]; then
  exec uv run vault-heist serve
else
  exec uv run vault-heist "$@"
fi
