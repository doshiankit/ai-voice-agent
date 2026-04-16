# AI Voice Agent
![Status](https://img.shields.io/badge/Status-Active%20Development-green)
![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![VoIP](https://img.shields.io/badge/VoIP-FreeSWITCH-orange)
![AI](https://img.shields.io/badge/AI-LLM%20%2B%20Voice-purple)

> Production-ready AI voice agent built on FreeSWITCH — handles real phone calls end-to-end using Speech-to-Text, LLM reasoning, and Text-to-Speech.

> ⚡ This project is under active development and evolving into a full AI Voice Platform (VoIP + LLM + Multi-Agent system)
---

## What This Does

When someone calls in, this system handles the entire conversation autonomously:

1. **FreeSWITCH** receives the SIP call and streams raw audio
2. **STT Service** (OpenAI Whisper) converts live speech to text in real time
3. **Agent Service** sends the transcript to an LLM for context-aware, intelligent response generation
4. **TTS Service** (Piper TTS) converts the LLM response back into natural speech
5. **FreeSWITCH** plays the audio back to the caller — completing the loop

**End-to-end latency:** ~1.5–2 seconds on CPU | ~800ms on GPU

---

## Features

### ✅ Completed

- [x] Real-time SIP call handling via FreeSWITCH  
- [x] Live Speech-to-Text (Whisper)  
- [x] LLM-based response generation (Groq / OpenAI)  
- [x] Text-to-Speech playback (Piper TTS)  
- [x] End-to-end call loop automation  
- [x] CPU & GPU auto-detection  
- [x] Supervisor-based service orchestration  
- [x] Call simulator for local testing  

---

### 🚧 In Progress
- [ ] Docker-based deployment  
- [ ] Streaming STT for lower latency  
- [ ] Multi-language support  
- [ ] Context memory across calls  
- [ ] Call analytics dashboard  

---

### 🔮 Planned

- [ ] Multi-agent orchestration (Supervisor + Agents)  
- [ ] CRM integration (HubSpot / Salesforce)  
- [ ] Voice biometrics / speaker identification  
- [ ] SaaS deployment (multi-tenant AI voice platform)
       
---
## Real-World Use Cases

### Telecom & Contact Centers
Replace legacy IVR systems with an AI agent that understands natural language — no more "press 1 for billing". Handles inbound support calls, account queries, and call routing without a human agent in the loop.

### Outbound Calling Campaigns
Automate outbound calls for appointment reminders, payment follow-ups, and customer surveys. The agent handles natural responses, objections, and can escalate to a live agent when needed.

### Hotel & Hospitality Automation
Front desk bot for handling room bookings, check-in queries, restaurant reservations, and local recommendations — available 24/7 without staffing costs.

### Healthcare Appointment Management
Automate appointment booking, rescheduling, and patient reminders. The agent can handle FAQs, collect basic intake information, and transfer complex cases to staff.

### Financial Services & Banking
Handle balance enquiries, transaction alerts, EMI reminders, and basic account support calls — integrated with your existing telephony infrastructure via SIP.

### Real Estate Lead Qualification
Automatically call and qualify inbound leads, ask discovery questions, schedule site visits, and log outcomes — before a human agent ever picks up the phone.

---

## Architecture

```
Caller (SIP Phone / PSTN)
        |
        v
  FreeSWITCH (SIP + RTP)
        |
        v
  Agent Service :8003
   /            \
  v              v
STT :8001     TTS :8002
(Whisper)    (Piper TTS)
        \      /
         v    v
        LLM (Groq / OpenAI)
```
---
## Call Flow (Optimized Architecture)

1. Incoming SIP call hits FreeSWITCH  
2. FreeSWITCH records/streams caller audio  
3. Audio is sent to a single **Agent API endpoint**  
4. Agent Service internally processes:
   - Speech-to-Text (Whisper)
   - LLM response generation
   - Text-to-Speech synthesis
5. Final audio response is returned to FreeSWITCH  
6. FreeSWITCH plays the response to the caller  

### Why Single Endpoint Design?

Instead of calling multiple services (STT → LLM → TTS) from FreeSWITCH,  
the system uses a unified Agent API.

**Advantages:**

- Reduces network latency (only one external API call)  
- Improves response time for real-time conversations  
- Keeps FreeSWITCH logic simple and clean  
- Enables internal optimization (GPU processing, batching, caching)  

---

## Services

| Service | Port | Technology | Description |
|---|---|---|---|
| FreeSWITCH | 5060 (SIP), 16384–16400 (RTP) | FreeSWITCH | SIP registration, call routing, media handling, ESL |
| STT Service | 8001 | OpenAI Whisper | Real-time speech-to-text. Auto-detects CPU or GPU. |
| TTS Service | 8002 | Piper TTS | Converts LLM text response to audio |
| Agent Service | 8003 | FastAPI + LLM | Core call logic — connects STT, LLM, TTS, and FreeSWITCH |
| Simulator Service | — | Custom | Call simulator for local testing without a real SIP endpoint |

---

## Tech Stack

- **Python** — FastAPI, Uvicorn, Whisper, Piper TTS
- **Lua** — FreeSWITCH call scripting
- **FreeSWITCH** — SIP/RTP media server
- **Groq / OpenAI** — LLM backend (pluggable)

---

## Prerequisites

- Ubuntu 22.04 LTS
- Root access
- Public IP (recommended for SIP registration)
- Python 3.10+

---

## Required Open Ports

| Port Range | Protocol | Service |
|---|---|---|
| 5060 | UDP/TCP | FreeSWITCH SIP (Signaling) |
| 16384–16400 | UDP | RTP (Media) |
| 8001 | TCP | STT Service |
| 8002 | TCP | TTS Service |
| 8003 | TCP | Agent Service |
| 8021 | TCP | FreeSWITCH ESL (Internal only) |

---

## Installation

```bash
cd /root
git clone https://github.com/doshiankit/ai-voice-agent.git
cd ai-voice-agent

cp .env.example .env
# Edit .env and add your API keys

chmod +x scripts/install.sh scripts/freeswitch_install.sh
./scripts/install.sh
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes (or OpenAI) | LLM backend — get free key at console.groq.com |
| `OPENAI_API_KEY` | Optional | Alternative LLM backend |
| `ESL_HOST` | Yes | FreeSWITCH ESL host (default: 127.0.0.1) |
| `ESL_PORT` | Yes | FreeSWITCH ESL port (default: 8021) |
| `ESL_PASSWORD` | Yes | FreeSWITCH ESL password (default: ClueCon) |
| `WHISPER_MODEL` | Yes | Model size: tiny / base / small / medium |

---

## What the Installer Does

The `install.sh` script fully automates setup:

- Installs system packages (build-essential, Python3, pip, ffmpeg, etc.)
- Installs FreeSWITCH with required modules
- Creates isolated Python virtual environments per service
- Auto-detects CPU or GPU — installs appropriate PyTorch version
- Pins NumPy to `2.1.2` for compatibility
- Configures Supervisor to manage all services
- Starts all services automatically on completion

---

## Verify Installation

```bash
# Check all services are running
supervisorctl status

# Expected output:
# agent_service      RUNNING
# stt_service        RUNNING
# tts_service        RUNNING
# simulator_service  RUNNING
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

# View live logs
tail -f /var/log/supervisor/agent_service.log
```

---

## Vast.ai Configuration

When deploying on Vast.ai GPU instances, open the following ports:

```
5060 UDP/TCP
16384-16400 UDP
8001-8003 TCP
```

---

## Project Structure

```
ai-voice-agent/
├── services/
│   ├── stt_service/         # Whisper speech-to-text
│   ├── tts_service/         # Piper text-to-speech
│   ├── agent_service/       # LLM call logic (core)
│   └── simulator_service/   # Call simulator for testing
├── freeswitch/              # FreeSWITCH dialplan + config + Lua scripts
├── scripts/
│   ├── install.sh           # Main installer
│   ├── freeswitch_install.sh
│   ├── start_all.sh
│   └── start_supervisor.sh
├── config/                  # Service configuration files
├── supervisor/              # Supervisor process configs
├── docker-compose.yml       # Docker orchestration
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
└── test_config.py           # Installation verification script
```

---

## Python Dependencies

Key packages pinned in `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.104.1 | Service API framework |
| uvicorn | 0.24.0 | ASGI server |
| openai-whisper | 20231117 | Speech-to-text |
| torch | 2.2.1 | ML runtime for Whisper |
| torchaudio | 2.2.1 | Audio processing |
| numpy | 2.1.2 | Numerical computing |
| pydantic | 2.12.5 | Data validation |
| tiktoken | 0.12.0 | Token counting |

> **Note:** Virtual environments are not committed to git. They are created by `install.sh` per service.

---

## Running with Docker

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f agent_service
```

---

## Testing

```bash
# Verify configuration and environment
python test_config.py

# Test STT service directly
curl -X POST http://localhost:8001/transcribe \
  -F "audio=@test_audio.wav"

# Test TTS service directly
curl -X POST http://localhost:8002/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, how can I help you today?"}'
```

---

## Notes

- CPU and GPU modes are handled automatically by the installer
- Designed for single-server deployment
- STT requires NumPy `2.1.2` — do not downgrade
- FreeSWITCH ESL port `8021` should not be exposed publicly

---

## Author

**Ankit Doshi** — 13 years VoIP/Telecom engineering  
FreeSWITCH | SIP | AI Voice | PHP | Python | Lua

[GitHub](https://github.com/doshiankit) · [LinkedIn](https://www.linkedin.com/in/ankit-doshi-b0507676/)

Any further improvements needed ? 
