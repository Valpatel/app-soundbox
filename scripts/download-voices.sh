#!/bin/bash
# Download all English Piper TTS voices
# Run from project root: bash scripts/download-voices.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VOICES_DIR="$PROJECT_ROOT/models/voices"

echo "=============================================="
echo "  Piper TTS Voice Downloader"
echo "=============================================="
echo ""

mkdir -p "$VOICES_DIR"

PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# All English voices (US and UK)
# Format: locale/name/quality
VOICES=(
    # US English - High quality voices
    "en_US/lessac/medium"
    "en_US/lessac/high"
    "en_US/lessac/low"
    "en_US/amy/medium"
    "en_US/amy/low"
    "en_US/arctic/medium"
    "en_US/hfc_male/medium"
    "en_US/hfc_female/medium"
    "en_US/joe/medium"
    "en_US/kusal/medium"
    "en_US/kristin/medium"
    "en_US/l2arctic/medium"
    "en_US/libritts/high"
    "en_US/libritts_r/medium"
    "en_US/ljspeech/medium"
    "en_US/ljspeech/high"
    "en_US/ryan/medium"
    "en_US/ryan/high"
    "en_US/ryan/low"

    # UK English
    "en_GB/alan/medium"
    "en_GB/alba/medium"
    "en_GB/aru/medium"
    "en_GB/cori/medium"
    "en_GB/cori/high"
    "en_GB/jenny_dioco/medium"
    "en_GB/northern_english_male/medium"
    "en_GB/semaine/medium"
    "en_GB/southern_english_female/medium"
    "en_GB/vctk/medium"
)

echo "Downloading ${#VOICES[@]} voice models to $VOICES_DIR"
echo ""

downloaded=0
skipped=0
failed=0

for voice_path in "${VOICES[@]}"; do
    # Convert path to filename: en_US/lessac/medium -> en_US-lessac-medium
    voice_name=$(echo "$voice_path" | tr '/' '-')
    onnx_file="$VOICES_DIR/${voice_name}.onnx"
    json_file="$VOICES_DIR/${voice_name}.onnx.json"

    if [ -f "$onnx_file" ]; then
        echo "[SKIP] $voice_name (already exists)"
        ((skipped++))
        continue
    fi

    echo -n "[DOWN] $voice_name... "

    # Download ONNX model
    if wget -q -O "$onnx_file" "$PIPER_BASE/$voice_path/$voice_name.onnx" 2>/dev/null; then
        # Download JSON config
        wget -q -O "$json_file" "$PIPER_BASE/$voice_path/$voice_name.onnx.json" 2>/dev/null || true
        echo "OK"
        ((downloaded++))
    else
        echo "FAILED"
        rm -f "$onnx_file" "$json_file"
        ((failed++))
    fi
done

echo ""
echo "=============================================="
echo "  Download Complete"
echo "=============================================="
echo "Downloaded: $downloaded"
echo "Skipped:    $skipped"
echo "Failed:     $failed"
echo ""
echo "Total voices available: $(ls -1 "$VOICES_DIR"/*.onnx 2>/dev/null | wc -l)"
echo ""
