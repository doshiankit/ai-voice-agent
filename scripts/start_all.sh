#!/bin/bash
echo "Starting Voice Services..."

Start STT service (8001)
cd services/stt
python stt_server.py --port 8001 --log-level info &
STT_PID=$!
echo "STT started (PID: $STT_PID) on port 8001"

Start TTS service (8002)
cd ../tts
python tts_server.py --port 8002 --voice en-us &
TTS_PID=$!
echo "TTS started (PID: $TTS_PID) on port 8002"

Start Agent service (8003)
cd ../agent
python agent_server.py --port 8003 --model small &
AGENT_PID=$!
echo "Agent started (PID: $AGENT_PID) on port 8003"

Save PIDs
echo "STT_PID=$STT_PID" > /tmp/ai_service_pids.env
echo "TTS_PID=$TTS_PID" >> /tmp/ai_service_pids.env
echo "AGENT_PID=$AGENT_PID" >> /tmp/ai_service_pids.env

echo "Services started successfully!"
echo "Use './scripts/stop_all.sh' to stop all services"
