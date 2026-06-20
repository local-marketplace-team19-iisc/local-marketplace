#!/usr/bin/env bash
# Pre-download the faster-whisper `base.en` model with plain curl, so we
# don't need Python's HTTPS stack to reach Hugging Face Hub. Useful behind
# enterprise TLS-inspection proxies (Cisco Secure Access, Zscaler, etc.)
# where brew Python's certifi bundle doesn't include the corporate root.
#
# Usage:
#   ./scripts/download_whisper_base_en.sh
#
# Result: files land in `models/faster-whisper-base.en/`, which is what
# `config/agent.yaml -> llm.asr.model_path` already points to.
#
# Total download size: ~140 MB (mostly model.bin).
# Idempotent: skips files that already exist with the right size.

set -euo pipefail

REPO="Systran/faster-whisper-base.en"
BASE_URL="https://huggingface.co/${REPO}/resolve/main"
DEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models/faster-whisper-base.en"

FILES=(
  "config.json"
  "model.bin"
  "tokenizer.json"
  "vocabulary.txt"
)

echo "Destination: $DEST_DIR"
mkdir -p "$DEST_DIR"

for f in "${FILES[@]}"; do
  out="$DEST_DIR/$f"
  url="$BASE_URL/$f"
  if [[ -s "$out" ]]; then
    echo "  ✓ already present: $f ($(du -h "$out" | cut -f1))"
    continue
  fi
  echo "  ↓ fetching: $f"
  # -L follows redirects (HF returns 302/307 to a CDN URL).
  # -fS makes curl fail on HTTP errors instead of writing the error body.
  # --retry handles transient blips.
  curl -fSL --retry 3 --retry-delay 2 \
       --progress-bar \
       -o "$out" \
       "$url"
done

echo
echo "Done. Verify with:"
echo "  ls -lh \"$DEST_DIR\""
