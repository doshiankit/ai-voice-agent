# AI Voice Agent

![Status](https://img.shields.io/badge/Status-Active%20Development-green)
![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![VoIP](https://img.shields.io/badge/VoIP-FreeSWITCH-orange)
![AI](https://img.shields.io/badge/AI-LLM%20%2B%20Voice-purple)

> Real-time AI voice agent for live SIP phone calls — Speech-to-Text → LLM → Text-to-Speech, end-to-end on a single CPU server.

---

## Measured Performance

| Step | Latency |
|---|---|
| Speech-to-Text (Whisper base) | ~0.6s |
| LLM response (Groq) | ~0.2s |
| Text-to-Speech (Piper) | ~0.2s |
| **End-to-end total** | **~1.5s on CPU** |

No GPU required. Tested on Hetzner CX32 (4 vCPU, 8GB RAM).

---

## What This Does

A caller speaks on a real SIP phone call. This system:

1. **FreeSWITCH** receives the SIP call and captures caller audio
2. **Pipeline Service** orchestrates the full flow in one request
3. **STT Service** transcribes the audio using faster-whisper
4. **Agent Service** sends the transcript to Groq LLM and returns a response
5. **TTS Service** converts the LLM response to speech using Piper TTS
6. **FreeSWITCH** plays the audio back to the caller

---

## Architecture

```
Caller (SIP Phone / PSTN)
        |
        v
  FreeSWITCH (port 5060 SIP, 16384-16400 RTP)
        |
        v
  Pipeline Service :8004  ← single entry point from FreeSWITCH
        |
        |---> STT Service :8001  (faster-whisper, CPU int8)
        |---> Agent Service :8003 (Groq LLM)
        |---> TTS Service :8002  (Piper TTS)
        |
        v
  Audio Response → FreeSWITCH → Caller
```

### Why Pipeline Service?

FreeSWITCH makes one HTTP call to Pipeline Service which internally
calls STT → Agent → TTS in sequence. This keeps FreeSWITCH logic
simple and all AI processing in one place.

---

## Services

| Service | Port | Technology | Description |
|---|---|---|---|
| FreeSWITCH | 5060 (SIP), 16384-16400 (RTP) | FreeSWITCH | SIP registration, call routing, ESL |
| Pipeline Service | 8004 | FastAPI | Orchestrates STT → Agent → TTS in one call |
| STT Service | 8001 | faster-whisper (CPU int8) | Converts caller speech to text |
| Agent Service | 8003 | FastAPI + Groq LLM | Generates intelligent response |
| TTS Service | 8002 | Piper TTS | Converts response text to audio |
| Simulator Service | — | Custom | Test calls without real SIP endpoint |

---

## Features

### Completed
- [x] Real-time SIP call handling via FreeSWITCH
- [x] Speech-to-Text using faster-whisper (CPU int8 optimised)
- [x] LLM response generation via Groq API (pluggable)
- [x] Text-to-Speech using Piper TTS
- [x] Single pipeline endpoint — one HTTP call from FreeSWITCH
- [x] Conversation memory within a call session
- [x] CPU and GPU auto-detection
- [x] Supervisor-based service orchestration
- [x] Docker support
- [x] Call simulator for local testing

### In Progress
- [ ] Streaming STT for lower latency
- [ ] Multi-language support
- [ ] Call analytics dashboard

### Planned
- [ ] Multi-agent orchestration
- [ ] CRM integration (HubSpot / Salesforce)
- [ ] Voice biometrics / speaker identification
- [ ] Multi-tenant SaaS deployment

---

## Real-World Use Cases

### Contact Center IVR Replacement
Replace legacy IVR with an AI agent that understands natural language.
Handles inbound support, account queries, and routing without human agents.

### Outbound Calling Campaigns
Automate appointment reminders, payment follow-ups, and surveys.
Handles natural responses and escalates to live agents when needed.

### Hotel & Hospitality
Front desk bot for room bookings, check-in queries, and recommendations.
Available 24/7 without staffing costs.

### Healthcare Appointment Management
Automate booking, rescheduling, and patient reminders.
Handles FAQs and transfers complex cases to staff.

### Financial Services
Balance enquiries, transaction alerts, EMI reminders via SIP.

### Real Estate Lead Qualification
Automatically call and qualify inbound leads, ask discovery questions,
schedule site visits, and log outcomes before a human agent picks up.

---

## Prerequisites

- Ubuntu 22.04 LTS
- Root access
- Public IP (required for SIP registration)
- Python 3.10+

---

## Required Open Ports

| Port | Protocol | Service |
|---|---|---|
| 5060 | UDP/TCP | FreeSWITCH SIP |
| 16384-16400 | UDP | RTP Media |
| 8001-8004 | TCP | AI Services |
| 8021 | TCP | FreeSWITCH ESL (internal only — do not expose publicly) |

---

## Installation

```bash
git clone https://github.com/doshiankit/ai-voice-agent.git
cd ai-voice-agent

cp .env.example .env
nano .env  # add your GROQ_API_KEY

chmod +x scripts/install.sh scripts/freeswitch_install.sh
./scripts/install.sh
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Get free key at console.groq.com |
| `GROQ_MODEL` | No | llama-3.1-8b-instant | Groq model name |
| `WHISPER_MODEL` | No | base | tiny / base / small / medium |
| `ESL_HOST` | No | 127.0.0.1 | FreeSWITCH ESL host |
| `ESL_PORT` | No | 8021 | FreeSWITCH ESL port |
| `ESL_PASSWORD` | No | ClueCon | FreeSWITCH ESL password |
| `STT_URL` | No | http://127.0.0.1:8001 | STT service URL |
| `AGENT_URL` | No | http://127.0.0.1:8003 | Agent service URL |
| `TTS_URL` | No | http://127.0.0.1:8002 | TTS service URL |
| `MAX_UPLOAD_MB` | No | 25 | Max audio upload size in MB |

---

## Verify Installation

```bash
supervisorctl status
# Expected output:
# agent_service      RUNNING
# pipeline_service   RUNNING
# stt_service        RUNNING
# tts_service        RUNNING

# Health checks
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

---

## Service Management

```bash
# Restart all services
supervisorctl restart all

# Stop all services
supervisorctl stop all

# Restart a single service
supervisorctl restart agent_service

# Live logs
tail -f /var/log/ai_agent/pipeline_service.err.log
tail -f /var/log/ai_agent/agent_service.out.log
tail -f /var/log/ai_agent/stt_service.err.log
tail -f /var/log/ai_agent/tts_service.err.log
```

---

## Testing

```bash
# Test full pipeline end-to-end (most important test)
curl -X POST http://localhost:8004/pipeline \
  -F "audio=@test_data/demo_audio.wav" \
  -F "session_id=test123" \
  -F "caller_id=1000" \
  -o response.wav \
  -w "Status: %{http_code} | Time: %{time_total}s\n"

# Test STT service only
curl -X POST http://localhost:8001/transcribe \
  -F "file=@test_data/demo_audio.wav" \
  -F "session_id=test123"

# Test Agent service only
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "How do I restart FreeSWITCH?", "conversation_id": "test123"}'

# Test TTS service only
curl -X POST "http://localhost:8002/synthesize?text=Hello+this+is+a+test" \
  -o test_output.wav
```

---

## Project Structure

```
ai-voice-agent/
├── services/
│   ├── stt_service/         # faster-whisper speech-to-text
│   ├── tts_service/         # Piper text-to-speech
│   ├── agent_service/       # Groq LLM response generation
│   ├── pipeline_service/    # Orchestrates STT → Agent → TTS
│   └── simulator_service/   # Call simulator for testing
├── freeswitch/              # FreeSWITCH dialplan, config, Lua scripts
├── scripts/
│   ├── install.sh           # Main installer (handles CPU/GPU detection)
│   └── freeswitch_install.sh
├── supervisor/              # Supervisor process configs per service
├── docker-compose.yml       # Docker orchestration
├── .env.example             # Environment variable template
└── test_config.py           # Installation verification script
```

---

## Running with Docker

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f pipeline_service
```

---

## Tech Stack

- **Python** — FastAPI, Uvicorn, faster-whisper, Piper TTS
- **Lua** — FreeSWITCH call scripting
- **FreeSWITCH** — SIP/RTP media server
- **Groq** — LLM backend (OpenAI-compatible, pluggable)

---

## Notes

- CPU and GPU modes are handled automatically by the installer
- Designed for single-server deployment — all services run on localhost
- STT requires NumPy 1.26.x — do not upgrade to 2.x
- FreeSWITCH ESL port 8021 must not be exposed publicly
- Ports 8001-8004 are internal services — expose only what your dialplan needs

---

## Contributing

Contributions welcome. Open an issue for discussion or submit a pull request.

---

## Author

**Ankit Doshi** — 13 years VoIP/Telecom engineering
FreeSWITCH | SIP | AI Voice | Python | Lua | PHP

[GitHub](https://github.com/doshiankit) · [LinkedIn](https://www.linkedin.com/in/ankit-doshi-b0507676/)

---

⭐ If you found this project useful, a star helps others discover it.
