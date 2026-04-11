# AI Voice Agent

AI Voice integration with FreeSWITCH SoftSwitch.

This project runs FreeSWITCH + STT + TTS + AI Agent on a single server (Hetzner CPU or Vast GPU supported).

---

## 1. INSTALLATION STEPS

**Server Requirements:**  
- Ubuntu 22.04 LTS  
- Root access  
- Public IP recommended  

**Required Open Ports:**

| Port Range        | Protocol | Service                         |
|-------------------|----------|---------------------------------|
| 5060              | UDP/TCP  | FreeSWITCH SIP (Signaling)      |
| 16384-16400       | UDP      | RTP (Media)                     |
| 8001              | TCP      | STT Service (Speech-to-Text)    |
| 8002              | TCP      | TTS Service (Text-to-Speech)    |
| 8003              | TCP      | Agent Service (AI Call Logic)   |
| 8021              | TCP      | FreeSWITCH ESL (Internal only)  |

**Install Everything:**

```bash
cd /root
git clone https://github.com/doshiankit/ai-voice-agent.git
cd ai-voice-agent

chmod +x scripts/install.sh scripts/freeswitch_install.sh
./scripts/install.sh
```
## 2. WHAT INSTALL DOES

The installation script (`install.sh`) performs the following tasks automatically:

- Installs required system packages (build-essential, Python3, pip, etc.)
- Installs FreeSWITCH with necessary modules
- Creates isolated Python virtual environments for each service
- Auto-detects CPU or GPU and installs the appropriate PyTorch version
- Pins NumPy to version 1.26.x for compatibility with PyTorch
- Configures Supervisor to manage all services
- Starts all services automatically after installation
  
 ## 3. SERVICE DETAILS

| Service           | Port  | Description                                                                                                 | Technology      |
|-------------------|-------|-------------------------------------------------------------------------------------------------------------|-----------------|
| FreeSWITCH        | —     | Handles SIP registration and call routing, RTP media handling, ESL connection for AI integration.           | FreeSWITCH      |
| STT Service       | 8001  | Converts speech to text using OpenAI Whisper. CPU/GPU auto-detected.                                       | OpenAI Whisper  |
| TTS Service       | 8002  | Converts AI text to speech audio using Piper TTS.                                                           | Piper TTS       |
| Agent Service     | 8003  | Handles AI call logic, communicates with STT and TTS, sends responses back to FreeSWITCH.                  | Custom AI logic |
| Simulator Service | —     | Used for testing and call simulation.                                                                       | —               |
  
--------------------------
  ## 4. VERIFY INSTALLATION
---------------------------
After installation, verify that all services are running correctly.

### Check Supervisor Status
```bash
supervisorctl status
```
  -----------------------
  ### 5. SERVICE MANAGEMENT
  -----------------------

Restart all services: ```supervisorctl restart all ```

Stop all services: ```supervisorctl stop all ```

  --------------------------
  ### 6. VAST.AI CONFIGURATION
  --------------------------

Open ports: 5060 UDP/TCP 16384-16400 UDP 8001-8003 TCP

  -----------------------------
  ### 7. PROJECT FOLDER STRUCTURE
  -----------------------------
```bash
ai-voice-agent/
├── services/
│   ├── stt_service/         # Whisper STT
│   ├── tts_service/         # Piper TTS
│   ├── agent_service/       # AI Agent logic
│   └── simulator_service/   # Call simulator
├── scripts/
│   ├── install.sh
│   ├── freeswitch_install.sh
│   ├── start_all.sh
│   └── start_supervisor.sh
├── configs/                 # Configuration files
├── web/                     # Web interfaces (Gradio)
├── tests/                   # Test scripts
└── docs/                    # Documentation


  -------
  NOTES
  -------

-   Virtual environments are NOT committed to git.
-   STT requires NumPy 1.26.x due to Torch compatibility.
-   Designed for single-server deployment.
-   CPU and GPU modes handled automatically.
