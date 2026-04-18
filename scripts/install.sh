#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# -----------------------------
# CONFIG (edit only this block)
# -----------------------------
REPO_URL="https://github.com/doshiankit/ai-voice-agent.git"

# -----------------------------
# STEP 1: Prerequisites
# -----------------------------
echo "▶ Installing prerequisites..."
apt update
apt install -y python3 python3-venv python3-pip git ffmpeg sox supervisor curl wget pciutils libsndfile1
sudo mkdir -p /var/log/ai_agent
sudo chown -R root:root /var/log/ai_agent
sudo chmod 755 /var/log/ai_agent
# -----------------------------
# STEP 2: Clone repo (if needed)
# -----------------------------
if [ ! -d "$PROJECT_DIR" ]; then
  echo "▶ Cloning repository..."
  git clone "$REPO_URL" "$PROJECT_DIR"
else
  echo "✔ Repo already exists, skipping clone"
  cd "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"
detect_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi >/dev/null 2>&1 && return 0
  fi
  [ -e /dev/nvidia0 ] && return 0
  if command -v lspci >/dev/null 2>&1; then
    lspci | grep -qi nvidia && return 0
  fi
  return 1
}

if detect_gpu; then
  INSTALL_MODE="gpu"
else
  INSTALL_MODE="cpu"
fi

echo "▶ Auto-detected install mode: $INSTALL_MODE"
# -----------------------------
# STEP: 3 Install FreeSWITCH (always, single-server mode)
# -----------------------------
read -p "Do you want to install FreeSWITCH? [Y/n]: " install_fs

# Default to "yes" if user just presses Enter
install_fs=${install_fs:-N}

if [[ "$install_fs" =~ ^[Yy]$ ]]; then
  if command -v freeswitch >/dev/null 2>&1 || [ -x /usr/local/freeswitch/bin/freeswitch ]; then
    echo "✔ FreeSWITCH already installed, skipping"
  else
    echo "▶ Installing FreeSWITCH..."
    chmod +x "$SCRIPT_DIR/freeswitch_install.sh"
    "$SCRIPT_DIR/freeswitch_install.sh"
  fi
else
  echo "⏭ Skipping FreeSWITCH installation"
fi
# -----------------------------
# STEP 4: Create venvs + install deps
# -----------------------------
echo "▶ Creating virtualenvs and installing dependencies..."

declare -A VENV_MAP=(
  ["stt_service"]="stt_venv"
  ["tts_service"]="tts_venv"
  ["agent_service"]="agent_venv"
  ["simulator_service"]="simulator_venv"
  ["pipeline_service"]="pipeline_venv"
)

for SERVICE in "${!VENV_MAP[@]}"; do
  VENV_NAME="${VENV_MAP[$SERVICE]}"
  SERVICE_DIR="services/$SERVICE"

  echo "  → $SERVICE"

  cd "$SERVICE_DIR"

  if [ ! -d "$VENV_NAME" ]; then
    python3 -m venv "$VENV_NAME"
  fi
  source "$VENV_NAME/bin/activate"
pip install --upgrade pip wheel

if [ "$SERVICE" = "stt_service" ]; then
  # (Optional) setuptools handling – can be kept, but faster-whisper doesn't require it
  pip uninstall -y setuptools >/dev/null 2>&1 || true
  pip install setuptools==68.2.2

  if [ "$INSTALL_MODE" = "cpu" ]; then
    echo "    ▶ Installing STT CPU requirements..."
    pip install --index-url https://pypi.org/simple \
            --extra-index-url https://download.pytorch.org/whl/cpu \
            -r requirements.cpu.txt
    # Install faster-whisper (CPU version will use CPU inference)
    pip install faster-whisper==1.0.3
  else
    echo "    ▶ Installing STT GPU requirements..."
    pip install -r requirements.gpu.txt
    # Install faster-whisper (GPU version will use CUDA automatically)
    pip install faster-whisper==1.0.3
  fi
else
  echo "    ▶ Installing standard requirements..."
  pip install -r requirements.txt
fi

deactivate
cd "$PROJECT_DIR"
done
rm -rf /root/.cache/pip || true
# -----------------------------
# STEP 5: Install Supervisor configs
# -----------------------------
echo "▶ Installing supervisor configurations..."
./scripts/start_supervisor.sh

echo "✅ Bootstrap completed successfully"
supervisorctl status

