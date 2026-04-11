#!/usr/bin/env bash
set -e

BASE_DIR="/root/ai-voice-agent"
SUP_SRC="$BASE_DIR/supervisor"
SUP_DST="/etc/supervisor/conf.d"

echo "▶ Copying supervisor configs..."
cp -v $SUP_SRC/*.conf $SUP_DST/

echo "▶ Reloading supervisor..."
supervisorctl reread
supervisorctl update

echo "▶ Starting core services..."
supervisorctl start stt_service || true
supervisorctl start tts_service || true
supervisorctl start agent_service || true

echo "✅ Services are up"
supervisorctl status

