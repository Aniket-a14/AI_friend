# Hardware Tuning & Optimization

Tips for maximizing performance, reducing latency, and keeping thermal headroom on workstations and laptops.

---

## 1. Memory Optimization on 16GB Machines

If you are running on a 16GB unified memory Apple Silicon Mac or 16GB Linux laptop:

* **Use `llama3.2:1b` or `llama3.2:3b`**: 3B models offer the optimal balance of reasoning depth and fast time-to-first-token ($<300\text{ms}$).
* **Disable Vision when not needed**: The Moondream VLM adds $\sim 1.7\text{ GB}$ of resident memory. Run `./start.sh full` without `--vision` for audio/text-only sessions.
* **Configure Docker Memory Ceiling**: Set Docker Desktop's memory limit to **8GB** in Docker Settings $\rightarrow$ Resources.

---

## 2. Low-Latency Audio Pacing (Rust STT)

To minimize speech turn-around time:
* Ensure `whisper.cpp` is using quantized weights (`ggml-tiny.en.bin` or `ggml-base.en.bin`).
* The fast speculative path (`SenseVoice`) runs in $<150\text{ms}$ on CPU using ONNX runtime multi-threading. Set `ONNX_NUM_THREADS=4` in `.env` for multi-core CPUs.

---

## 3. GPU Acceleration with Colab

If your workstation runs hot during long sessions, offload heavy voice fine-tuning or model benchmarking to a Google Colab GPU runtime using our [Colab GPU Acceleration Guide](/docs/guides/colab-gpu-acceleration).
