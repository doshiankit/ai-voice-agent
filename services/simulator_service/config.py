import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # =========================
    # Core Service URLs
    # =========================
    STT_SERVICE_URL = os.getenv(
        "STT_SERVICE_URL",
        "http://127.0.0.1:8001/transcribe"
    )

    TTS_SERVICE_URL = os.getenv(
        "TTS_SERVICE_URL",
        "http://127.0.0.1:8002/synthesize"
    )

    AGENT_SERVICE_URL = os.getenv(
        "AGENT_SERVICE_URL",
        "http://127.0.0.1:8003/chat"
    )

    # =========================
    # Health Check URLs
    # =========================
    STT_HEALTH_URL = os.getenv(
        "STT_HEALTH_URL",
        "http://127.0.0.1:8001/health"
    )

    TTS_HEALTH_URL = os.getenv(
        "TTS_HEALTH_URL",
        "http://127.0.0.1:8002/health"
    )

    AGENT_HEALTH_URL = os.getenv(
        "AGENT_HEALTH_URL",
        "http://127.0.0.1:8003/health"
    )

config = Config()

