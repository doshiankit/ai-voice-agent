#!/usr/bin/env python3
"""
Simulator Service — test the AI Voice Agent pipeline without a real SIP phone.

Usage:
    # Test with existing WAV file
    python app.py --wav /path/to/audio.wav

    # Run multi-turn conversation using WAV files
    python app.py --conversation

    # Check all services are healthy
    python app.py --health
"""
import argparse
import os
import sys
import time
import uuid
import requests
from pathlib import Path
from config import config

def print_separator():
    print("-" * 60)

def check_health():
    """Check all services are running before testing."""
    services = {
        "STT   :8001": config.STT_HEALTH_URL,
        "TTS   :8002": config.TTS_HEALTH_URL,
        "Agent :8003": config.AGENT_HEALTH_URL,
        "Pipeline :8004": config.PIPELINE_HEALTH_URL,
    }

    print("\nChecking service health...")
    print_separator()
    all_healthy = True

    for name, url in services.items():
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"  OK      {name}")
            else:
                print(f"  FAIL    {name}  (status {resp.status_code})")
                all_healthy = False
        except requests.exceptions.ConnectionError:
            print(f"  DOWN    {name}  (not reachable)")
            all_healthy = False
        except Exception as e:
            print(f"  ERROR   {name}  ({e})")
            all_healthy = False

    print_separator()
    if all_healthy:
        print("All services healthy. Ready to test.\n")
    else:
        print("Some services are down. Run: supervisorctl status\n")
    return all_healthy


def call_pipeline(wav_path: str, session_id: str = None, caller_id: str = "simulator"):
    """
    Send a WAV file through the full pipeline.
    Returns dict with transcript, response, audio_path, latency.
    """
    if not os.path.exists(wav_path):
        print(f"ERROR: WAV file not found: {wav_path}")
        return None

    session_id = session_id or str(uuid.uuid4())[:8]

    print(f"\nSession  : {session_id}")
    print(f"Audio    : {wav_path}")
    print(f"Sending to pipeline...")

    t_start = time.perf_counter()

    try:
        with open(wav_path, "rb") as f:
            resp = requests.post(
                config.PIPELINE_URL,
                files={"audio": (os.path.basename(wav_path), f, "audio/wav")},
                data={"session_id": session_id, "caller_id": caller_id},
                timeout=30,
            )
    except requests.exceptions.ConnectionError:
        print("ERROR: Pipeline service not reachable. Is it running?")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

    total_time = time.perf_counter() - t_start

    if resp.status_code != 200:
        print(f"ERROR: Pipeline returned {resp.status_code}")
        print(resp.text[:300])
        return None

    # Extract info from response headers
    transcript = resp.headers.get("X-Transcript", "(not available)")
    duration   = resp.headers.get("X-Pipeline-Duration", f"{total_time:.3f}")

    # Save audio response
    output_path = str(config.TEST_DATA_DIR / f"response_{session_id}.wav")
    with open(output_path, "wb") as f:
        f.write(resp.content)

    return {
        "session_id"  : session_id,
        "transcript"  : transcript,
        "latency"     : float(duration),
        "audio_bytes" : len(resp.content),
        "audio_path"  : output_path,
    }


def print_result(result: dict):
    """Print pipeline result in a readable format."""
    print_separator()
    print(f"  Transcript : {result['transcript']}")
    print(f"  Latency    : {result['latency']:.2f}s end-to-end")
    print(f"  Audio out  : {result['audio_bytes']} bytes → {result['audio_path']}")
    print_separator()


def run_single(wav_path: str):
    """Test pipeline with a single WAV file."""
    check_health()
    result = call_pipeline(wav_path)
    if result:
        print_result(result)


def run_conversation():
    """
    Simulate a multi-turn conversation.
    Uses demo_audio.wav repeatedly with different session context.
    In a real scenario you would provide different WAV files per turn.
    """
    demo_wav = str(config.TEST_DATA_DIR / "demo_audio.wav")
    if not os.path.exists(demo_wav):
        print(f"ERROR: demo_audio.wav not found at {demo_wav}")
        print("Add a test WAV file to test_data/ directory first.")
        return

    check_health()

    session_id = str(uuid.uuid4())[:8]
    print(f"\nStarting multi-turn conversation (session: {session_id})")
    print("Using demo_audio.wav for each turn.")
    print("In production, provide different WAV per turn.\n")

    latencies = []

    for turn in range(1, 4):
        print(f"\n--- Turn {turn} ---")
        result = call_pipeline(demo_wav, session_id=session_id)
        if result:
            print_result(result)
            latencies.append(result["latency"])
        else:
            print(f"Turn {turn} failed.")
            break
        time.sleep(1)

    if latencies:
        print_separator()
        print(f"  Turns completed : {len(latencies)}")
        print(f"  Average latency : {sum(latencies)/len(latencies):.2f}s")
        print(f"  Min latency     : {min(latencies):.2f}s")
        print(f"  Max latency     : {max(latencies):.2f}s")
        print_separator()


def run_latency_benchmark(wav_path: str, runs: int = 5):
    """Run pipeline N times and report latency statistics."""
    check_health()
    print(f"\nRunning {runs}-call latency benchmark...")
    print_separator()

    latencies = []
    for i in range(1, runs + 1):
        result = call_pipeline(wav_path, session_id=f"bench_{i}")
        if result:
            latencies.append(result["latency"])
            print(f"  Run {i}: {result['latency']:.2f}s  |  {result['transcript'][:50]}")
        else:
            print(f"  Run {i}: FAILED")
        time.sleep(1)

    if latencies:
        print_separator()
        print(f"  Runs completed  : {len(latencies)}/{runs}")
        print(f"  Average latency : {sum(latencies)/len(latencies):.2f}s")
        print(f"  Min latency     : {min(latencies):.2f}s")
        print(f"  Max latency     : {max(latencies):.2f}s")
        under_2s = sum(1 for l in latencies if l < 2.0)
        print(f"  Under 2 seconds : {under_2s}/{len(latencies)} calls")
        print_separator()


def main():
    parser = argparse.ArgumentParser(
        description="AI Voice Agent Simulator — test pipeline without SIP phone"
    )
    parser.add_argument(
        "--wav",
        help="Path to WAV file to send through pipeline",
        default=None
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Check all services are healthy"
    )
    parser.add_argument(
        "--conversation",
        action="store_true",
        help="Run multi-turn conversation simulation"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run 5-call latency benchmark"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of runs for benchmark (default: 5)"
    )

    args = parser.parse_args()

    # Default: use demo_audio.wav if no WAV specified
    wav_path = args.wav or str(config.TEST_DATA_DIR / "demo_audio.wav")

    if args.health:
        check_health()
    elif args.conversation:
        run_conversation()
    elif args.benchmark:
        run_latency_benchmark(wav_path, runs=args.runs)
    else:
        # Default: single call test
        run_single(wav_path)


if __name__ == "__main__":
    main()
