# Colab GPU Acceleration & Remote Development

You can connect free or rented cloud GPUs (Google Colab, Lambda Labs, RunPod) to your local development environment to offload model training, heavy benchmark runs, or LLM inference without heating up your workstation.

---

## Bundled Colab Notebooks

AI Friend ships three production-ready Colab notebooks in `notebooks/`:

| Notebook | Purpose | GPU Tier |
| :--- | :--- | :--- |
| **`01_voice_clone_sovits_training.ipynb`** | GPT-SoVITS voice fine-tuning & weight quantization. | Free T4 GPU |
| **`02_llm_benchmark_and_eval_harness.ipynb`** | Probe evaluation, Recall@K scoring, and latency profiling. | T4 / A100 |
| **`03_end_to_end_mesh_gpu_runner.ipynb`** | Full 9-agent headless mesh deployment with WebSocket bridge. | A100 / High-RAM |

---

## Connecting Local VS Code to Colab GPU (Remote SSH)

You can edit files and run terminal commands directly on a Colab GPU from your local VS Code.

### Step 1: In Google Colab
Run this snippet in a new Colab cell to create a secure Cloudflare SSH tunnel:

```python
!pip install colab_ssh --upgrade
from colab_ssh import launch_ssh_cloudflared
launch_ssh_cloudflared(password="my_secure_password")
```

Colab will output your SSH config block:
```text
Host colab
    HostName <tunnel-id>.trycloudflare.com
    User root
    Port 22
```

### Step 2: In Local VS Code
1. Install the official **Remote - SSH** extension.
2. Open `~/.ssh/config` and paste the snippet from Colab.
3. Press `Cmd+Shift+P` $\rightarrow$ `Remote-SSH: Connect to Host...` $\rightarrow$ `colab`.
4. Enter your password.

You now have a live terminal and full filesystem access inside the Colab GPU runtime.

