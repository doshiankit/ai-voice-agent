import sys
sys.path.append('/root/ai-voice-agent')
from config import config, debug_config

debug_config()

# Test that URLs are correct
print(f"\nTesting URLs...")
print(f"STT_SERVICE_URL: {config.STT_SERVICE_URL}")
print(f"TTS_SERVICE_URL: {config.TTS_SERVICE_URL}")
print(f"OLLAMA_URL: {config.OLLAMA_URL}")
