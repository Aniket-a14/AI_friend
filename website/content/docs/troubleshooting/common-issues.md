# Common Issues & Playbooks

A guide to diagnosing and resolving common operational issues encountered during local development.

---

## 1. Port 5432 / 7687 / 6379 Already in Use

### Symptom:
`docker compose up` fails with:
`Bind for 0.0.0.0:5432 failed: port is already allocated`

### Solution:
You may have a host-native PostgreSQL, Neo4j, or Redis service running locally.
* On macOS: Stop local services via `brew services stop postgresql` or `brew services stop redis`.
* Or update port bindings in `.env` to map to alternative host ports (e.g. `DATABASE_URL=postgresql://ai_friend:ai_friend@127.0.0.1:5433/ai_friend`).

---

## 2. Ollama Model Not Found / Connection Refused

### Symptom:
`brain_agent` logs: `Cannot connect to Ollama at http://host.docker.internal:11434`

### Solution:
1. Ensure Ollama is running on the host: `ollama serve`.
2. Confirm the model has been pulled: `ollama pull llama3.2:3b`.
3. If running Linux, ensure `OLLAMA_BASE_URL` in `.env` is set to `http://172.17.0.1:11434` (host gateway) instead of `host.docker.internal`.

---

## 3. Reference Voice Sample Missing / Healthcheck Fail

### Symptom:
`local_voice` container stays in `(unhealthy)` state and `voice_agent` does not start.

### Solution:
1. AI Friend boots automatically with a default voice sample if missing. Ensure `assets/voice/default_voice.wav` exists.
2. Run `python backend/scripts/ensure_default_voice_sample.py` to re-seed the reference audio.
3. Restart `local_voice`: `docker compose -f docker-compose.infra.yml restart local_voice`.

---

## 4. Microphone Input Permissions (macOS)

### Symptom:
`scripts/audio/record_voice.py` records silence or throws `PortAudioError: Permission Denied`.

### Solution:
* Open **System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Microphone**.
* Ensure Terminal, iTerm2, or VS Code has microphone access enabled.
