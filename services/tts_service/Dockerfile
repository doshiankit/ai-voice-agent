FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Piper and audio handling
RUN apt-get update && apt-get install -y \
    wget \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download a small, default English voice model for Piper (optional, can be runtime)
RUN wget -O /app/voices/en_US-lessac-medium.onnx https://github.com/rhasspy/piper/releases/download/v0.0.2/en_US-lessac-medium.onnx \
    && wget -O /app/voices/en_US-lessac-medium.onnx.json https://github.com/rhasspy/piper/releases/download/v0.0.2/en_US-lessac-medium.onnx.json

EXPOSE 8002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
