# Privacy & Data Sovereignty

AI Friend is architected under the principle of **absolute local data sovereignty**: your companion belongs to you, and your private conversations belong on your machine.

---

## The Zero-Leak Guarantee

* **No Cloud Accounts**: There is no sign-up, no login wall, and no centralized user database.
* **No Telemetry**: The codebase contains zero analytics tracking, phone-home beacons, or usage reporting.
* **Local Confinement**: All databases (Postgres, Neo4j, Redis, Qdrant) bind strictly to `127.0.0.1`.
* **Local Models**: Ollama LLM, whisper.cpp STT, and GPT-SoVITS voice synthesis run entirely in local memory.

---

## Where Your Data Lives

All state is persisted in local files and Docker volumes on your host disk:

| Data Category | Local Storage Location | What is Stored |
| :--- | :--- | :--- |
| **Authored Persona** | `personal/persona.toml` (gitignored) | Your original prose description and initial preferences. |
| **Biography Memory** | `personal/biography.md` (gitignored) | Background documentary context. |
| **Episodic Memories** | Docker volume `pgdata` (Postgres) | Vector embeddings and historical conversation turns. |
| **Knowledge Graph** | Docker volume `neo4j_data` (Neo4j) | Entity relationships and preference networks. |
| **Affect & Weights** | `backend/state_cache.db` (SQLite) | Durable PAD baseline values and adaptive learning weights. |
| **Voice Recordings** | `backend/voice_samples/` | Enrolled reference WAV audio files. |

---

## Complete Export & Data Portability

You are never locked into a hardware machine. AI Friend includes single-command backup and restore tools (`scripts/export_friend.py` / `scripts/import_friend.py`) that package all four datastores into an encrypted, portable `.tar.gz` archive.

```bash
# Export complete friend snapshot
python backend/scripts/export_friend.py --out my_friend_backup.tar.gz

# Restore on a new computer
python backend/scripts/import_friend.py --archive my_friend_backup.tar.gz --force
```
