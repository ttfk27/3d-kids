#!/usr/bin/env bash
# Install MoneyPrinterTurbo (pinned) next to mptpro and configure it for local Ollama + Kokoro.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MPT_SHA="4204d0f39afa8ada6f3edc31604141f959fe254e"   # upstream commit this layer was tested against
MPT_DIR="${MPT_DIR:-$HERE/upstream/MoneyPrinterTurbo}"

command -v uv >/dev/null || { echo "install uv first: https://docs.astral.sh/uv/"; exit 1; }
command -v ffmpeg >/dev/null || { echo "install ffmpeg first"; exit 1; }

if [ ! -d "$MPT_DIR/.git" ]; then
  mkdir -p "$(dirname "$MPT_DIR")"
  git clone https://github.com/harry0703/MoneyPrinterTurbo.git "$MPT_DIR"
fi
git -C "$MPT_DIR" fetch --quiet origin "$MPT_SHA" 2>/dev/null || true
git -C "$MPT_DIR" checkout --quiet "$MPT_SHA"
(cd "$MPT_DIR" && uv sync --frozen)

uv venv --quiet "$HERE/.venv" 2>/dev/null || true
uv pip install --quiet --python "$HERE/.venv/bin/python" -e "$HERE[captions,youtube,dev]"

"$HERE/.venv/bin/mptpro" mpt-config --mpt-dir "$MPT_DIR" \
  --ollama-model "${OLLAMA_MODEL:-qwen2.5:14b-instruct}" \
  --kokoro-url "${KOKORO_URL:-http://127.0.0.1:8880/v1}" \
  --subtitle-provider "${SUBTITLE_PROVIDER:-}" --whisper-device "${WHISPER_DEVICE:-cuda}"

cat <<MSG

Done. Start MoneyPrinterTurbo:   (cd "$MPT_DIR" && uv run python main.py)
Then:  source "$HERE/.venv/bin/activate" && mptpro init && mptpro doctor
MSG
