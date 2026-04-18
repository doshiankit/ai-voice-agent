import os
from dotenv import load_dotenv
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=project_root / '.env')

class Config:
    # Pipeline is the single entry point — do not call STT/Agent/TTS directly
    PIPELINE_URL = os.getenv("PIPELINE_URL", "http://127.0.0.1:8004/pipeline")

    # Health checks for all services
    STT_HEALTH_URL    = os.getenv("STT_URL",      "http://127.0.0.1:8001") + "/health"
    TTS_HEALTH_URL    = os.getenv("TTS_URL",      "http://127.0.0.1:8002") + "/health"
    AGENT_HEALTH_URL  = os.getenv("AGENT_URL",    "http://127.0.0.1:8003") + "/health"
    PIPELINE_HEALTH_URL = os.getenv("PIPELINE_URL", "http://127.0.0.1:8004") + "/health"

    # Simulator settings
    TEST_DATA_DIR = project_root / "test_data"

config = Config()
