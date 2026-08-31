# Dedicated 24/7 AI / GPU Server Runbook

A production-hardened engineering guide for configuring an on-premises dedicated Ubuntu machine with an NVIDIA GPU for continuous, low-latency AI compute, LLM serving, and real-time voice synthesis.

---

## 🧭 The 5-Tier Configuration Hierarchy

To ensure system stability, every operational recommendation follows a strict 5-tier classification:

```text
 Tier 1 ──► [REQUIRED BASELINE]         Essential for functional boot, basic security, and driver operation.
 Tier 2 ──► [RECOMMENDED STANDARD]      Low-risk operational improvements beneficial across all environments.
 Tier 3 ──► [WORKLOAD-SPECIFIC]         Configure ONLY when running that specific AI framework or model type.
 Tier 4 ──► [BENCHMARK-DRIVEN TUNING]   Must be measured and calibrated on your specific silicon before persisting.
 Tier 5 ──► [DO NOT APPLY BLINDLY]      Hardware-, kernel-, or environment-dependent; requires prior validation.
```

---

## ⚡ Step 1: Motherboard Firmware (BIOS / UEFI)

`[Tier 1: Required Baseline]` & `[Tier 2: Recommended Standard]`

| Firmware Setting | Value | Tier | Technical Purpose & Behavior |
| :--- | :--- | :--- | :--- |
| **`Restore on AC Power Loss` / `AC BACK`** | **`Always On`** | `Tier 1` | Automatically reboots the machine when wall power is restored after an outage. |
| **`Above 4G Decoding`** | **`Enabled`** | `Tier 1` | Maps 64-bit PCIe memory apertures above 4GB line for high-memory GPU compute. |
| **`Resizable BAR (ReBAR)`** | **`Enabled`** | `Tier 2` | Allows dynamic 64-bit PCIe BAR mapping for direct CPU-to-VRAM memory access. |
| **`Fast Boot`** | **`Disabled`** | `Tier 2` | Forces full PCIe hardware link training on every boot to prevent driver drops. |

---

## 🛡️ Step 2: Base OS & Zero-Trust Security Baseline

`[Tier 1: Required Baseline]`

### 1. SSH Server Hardening (`/etc/ssh/sshd_config.d/99-hardened.conf`)
```ini
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
MaxAuthTries 3
```

### 2. Zero-Trust UFW Firewall
```bash
# Dynamically detect primary Ethernet interface
PRIMARY_IFACE=$(ip -o -4 route show to default | awk '{print $5}')

sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on lo
sudo ufw allow in on tailscale0
sudo ufw allow in on "$PRIMARY_IFACE" to any port 22 proto tcp
sudo ufw enable
```

### 3. Mask Sleep Targets for 24/7 Headless Operation
```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

---

## 🎮 Step 3: NVIDIA Driver & Container Passthrough

`[Tier 1: Required Baseline]`

### 1. Dynamic Driver Installation
```bash
sudo ubuntu-drivers list
sudo ubuntu-drivers install
sudo reboot
```

### 2. Docker & NVIDIA Container Toolkit
```bash
# Install NVIDIA Container Toolkit
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU container execution
docker run --rm --gpus all ubuntu:22.04 nvidia-smi
```

---

## ⚡ Step 4: Benchmark-Driven GPU Power Capping

`[Tier 4: Benchmark-Driven Tuning]`

1. Query supported limits: `nvidia-smi -q -d POWER | grep -Ei 'power limit'`
2. Benchmark tokens/sec at factory TDP.
3. Lower power limit in **10W increments** (e.g., 184W $\to$ 160W $\to$ 140W).
4. Select the inflection point where power/thermals drop by 20–30% with **< 2% loss in compute throughput**.

Apply the measured power limit:
```bash
sudo nvidia-smi -pl <measured_watts>
```

---

## 🧠 Step 5: Secure AI Workload Serving

`[Tier 3: Workload-Specific]`

### Ollama Model Serving
Always bind unauthenticated serving endpoints strictly to `127.0.0.1`:

```ini
# /etc/systemd/system/ollama.service.d/environment.conf
[Service]
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_HOST=127.0.0.1:11434"
```

Restart Ollama:
```bash
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

---

## 📊 Live System Verification Checklist

- [x] **BIOS**: `AC BACK: Always On`, `Above 4G / ReBAR: Enabled`.
- [x] **OS**: Sleep targets masked, physical monitor unplugged (saving ~60–350MB display VRAM).
- [x] **Security**: SSH keys enforced, UFW default deny active, services bound to `127.0.0.1`.
- [x] **Networking**: Tailscale WireGuard mesh active with direct peer-to-peer connection.
- [x] **GPU Driver**: Verified kernel-matched driver with `nvidia-persistenced.service` active.
- [x] **Runtimes**: Docker Engine with NVIDIA Container Toolkit passthrough enabled.
