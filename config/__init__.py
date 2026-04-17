import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """
    Centralized configuration for AI Voice Agent.
    All service URLs and settings are defined here.
    """
    
    # Basic configuration from environment variables
    STT_HOST = os.getenv('STT_HOST', 'localhost')
    STT_PORT = int(os.getenv('STT_PORT', '8001'))
    
    TTS_HOST = os.getenv('TTS_HOST', 'localhost')
    TTS_PORT = int(os.getenv('TTS_PORT', '8002'))
    
    # Base URLs (constructed from host and port)
    @property
    def STT_BASE_URL(self):
        return f"http://{self.STT_HOST}:{self.STT_PORT}"
    
    @property
    def TTS_BASE_URL(self):
        return f"http://{self.TTS_HOST}:{self.TTS_PORT}"
    
    @property
    def STT_TRANSCRIBE_URL(self):
        return f"{self.STT_BASE_URL}/transcribe"
    
    @property
    def STT_HEALTH_URL(self):
        return f"{self.STT_BASE_URL}/health"
    
    @property
    def TTS_SYNTHESIZE_URL(self):
        return f"{self.TTS_BASE_URL}/synthesize"
    
    @property
    def TTS_HEALTH_URL(self):
        return f"{self.TTS_BASE_URL}/health"
    
    
    # Alias for backward compatibility (use these in simulate_call.py)
    @property
    def STT_SERVICE_URL(self):
        """Alias for STT_TRANSCRIBE_URL"""
        return self.STT_TRANSCRIBE_URL
    
    @property
    def TTS_SERVICE_URL(self):
        """Alias for TTS_SYNTHESIZE_URL"""
        return self.TTS_SYNTHESIZE_URL
    


# Create a singleton instance
config = Config()


def debug_config():
    """Print current configuration for debugging"""
    print("=" * 50)
    print("AI Voice Agent Configuration")
    print("=" * 50)
    print(f"STT Service: {config.STT_BASE_URL}")
    print(f"  - Health: {config.STT_HEALTH_URL}")
    print(f"  - Transcribe: {config.STT_TRANSCRIBE_URL}")
    print(f"TTS Service: {config.TTS_BASE_URL}")
    print(f"  - Health: {config.TTS_HEALTH_URL}")
    print(f"  - Synthesize: {config.TTS_SYNTHESIZE_URL}")
    print("=" * 50)


# Run debug if this file is executed directly
if __name__ == "__main__":
    debug_config()
