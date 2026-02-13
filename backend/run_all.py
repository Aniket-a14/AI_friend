import asyncio
import subprocess
import sys
import os
import signal
import logging

# Configure basic logging for the orchestrator
logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("MeshRunner")

# Detect virtual environment python
def get_python_executable():
    venv_path = os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_path):
        return venv_path
    return sys.executable

PYTHON_EXE = get_python_executable()
logger.info(f"Using Python: {PYTHON_EXE}")

# List of commands to run
COMMANDS = [
    # 1. Signaling Server
    {
        "name": "Signaling",
        "cmd": [PYTHON_EXE, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        "cwd": os.getcwd()
    },
    # 2. Transport Agent (Bridges WebRTC to NATS)
    {
        "name": "Transport",
        "cmd": [PYTHON_EXE, "-m", "app.agents.transport_agent"],
        "cwd": os.getcwd()
    },
    # 3. STT Agent (Whisper processing)
    {
        "name": "STT",
        "cmd": [PYTHON_EXE, "-m", "app.agents.stt_agent"],
        "cwd": os.getcwd()
    },
    # 4. Brain Agent (Reasoning & RAG)
    {
        "name": "Brain",
        "cmd": [PYTHON_EXE, "-m", "app.agents.brain_agent"],
        "cwd": os.getcwd()
    },
    # 5. Voice Agent (GPT-SoVITS TTS)
    {
        "name": "Voice",
        "cmd": [PYTHON_EXE, "-m", "app.agents.voice_agent"],
        "cwd": os.getcwd()
    },
    # 6. Vision Agent (Screen/Camera capture)
    {
        "name": "Vision",
        "cmd": [PYTHON_EXE, "-m", "app.agents.vision_agent"],
        "cwd": os.getcwd()
    }
]

async def run_process(name, cmd, cwd):
    """Run a subprocess and pipe its output to the main console."""
    logger.info(f"Starting {name}...")
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def log_stream(stream, prefix):
            try:
                while True:
                    try:
                        line = await stream.readline()
                        if not line:
                            break
                        text = line.decode('utf-8', errors='replace').strip()
                        if text:
                            print(f"[{prefix}] {text}", flush=True)
                    except (ValueError, OSError, asyncio.CancelledError, RuntimeError):
                        break
            except Exception:
                pass

        # Create tasks for logging
        stdout_task = asyncio.create_task(log_stream(process.stdout, name))
        stderr_task = asyncio.create_task(log_stream(process.stderr, name))

        try:
            exit_code = await process.wait()
            logger.info(f"{name} exited with code {exit_code}")
        finally:
            # Shield cancellation to ensure we don't hit closed pipe errors
            stdout_task.cancel()
            stderr_task.cancel()
            try:
                await asyncio.wait([stdout_task, stderr_task], timeout=0.1)
            except:
                pass
            
    except Exception as e:
        logger.error(f"Failed to start {name}: {e}")

async def main():
    logger.info("🌊 Launching Sovereign Mesh...")
    
    # 1. Ensure NATS streams are configured first
    logger.info("Initializing NATS infrastructure...")
    try:
        setup_script = os.path.join("scripts", "setup_nats_streams.py")
        # Run setup and wait for it
        proc = await asyncio.create_subprocess_exec(
            sys.executable, setup_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        stdout, _ = await proc.communicate()
        if stdout:
            print(stdout.decode(), flush=True)
            
        if proc.returncode == 0:
            logger.info("NATS infrastructure ready.")
        else:
            logger.error(f"NATS setup failed with exit code {proc.returncode}")
            return
    except Exception as e:
        logger.error(f"NATS setup failed: {e}")
        return

    # 2. Run all processes in parallel
    tasks = []
    for service in COMMANDS:
        tasks.append(run_process(service["name"], service["cmd"], service["cwd"]))
    
    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down mesh...")
    except Exception as e:
        logger.error(f"Mesh error: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        # ProactorEventLoop is required for subprocess pipes on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Orchestrator failed: {e}")
