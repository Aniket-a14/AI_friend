# REST API Reference

The backend exposes authenticated FastAPI REST service routers under `/api/` (implemented in `backend/app/api/`).

---

## 1. Persona Management (`/api/persona`)

### `GET /api/persona/live`
Reads the friend's currently evolved personality directly from the durable PostgreSQL configuration store, reflecting relationship depth, trust, and adaptive traits rather than the initial seed file.

* **Response (200 OK)**:
  ```json
  {
    "persona": {
      "name": "Maya",
      "valence_baseline": 0.35,
      "arousal_baseline": 0.55,
      "dominance_baseline": 0.60,
      "cortisol_sensitivity": 0.35,
      "dopamine_sensitivity": 0.80,
      "traits": ["Loyalty", "Directness", "Banter"],
      "avoid": ["Sycophancy", "Corporate Fluff"]
    },
    "immutable_core": {
      "honesty": true,
      "privacy": true,
      "safety_boundaries": ["anti-harm", "anti-exfiltration"]
    },
    "relationship": "Childhood Best Friend",
    "seeded_from_file": "personal/persona.toml"
  }
  ```

---

### `POST /api/persona/compile`
Translates freeform natural language description prose into a validated, previewable `PersonaProfile`. **Stateless** — nothing is written to disk.

* **Request Body** (`application/json`):
  ```json
  {
    "description": "She's blunt, hates small talk, grew up with me in Montreal, and gets annoyed when I dodge technical questions."
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "profile": {
      "name": "Alex",
      "valence_baseline": 0.10,
      "arousal_baseline": 0.45,
      "dominance_baseline": 0.60,
      "traits": ["Directness", "Dry Sarcasm"],
      "avoid": ["Small Talk", "Evasiveness"]
    },
    "biography_markdown": "# Biography\n...",
    "inferences": [
      { "field": "dominance_baseline", "value": 0.60, "rationale": "Blunt demeanor implies high conversational agency." }
    ],
    "dimensions": { ... },
    "immutable_core": { ... }
  }
  ```

---

### `POST /api/persona/dry-run-chat`
Simulates a single test turn against a compiled (not yet saved) persona voice without memory or affect dependencies.

* **Request Body** (`application/json`):
  ```json
  {
    "profile": { ... },
    "message": "I'm thinking of skipping writing unit tests for this feature."
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "reply": "Please don't. You know you'll be debugging that in production by midnight. Write the test."
  }
  ```

---

### `POST /api/persona/commit`
The one-way door: validates and saves the approved persona to `personal/persona.toml` and `personal/biography.md`, pointing `.env` at them.

* **Request Body** (`application/json`):
  ```json
  {
    "profile": { ... },
    "biography_markdown": "# Biography\n...",
    "force": false
  }
  ```

---

## 2. Memory Inspection (`/api/memory`)

### `GET /api/memory/recent`
Returns paginated episodic memories directly from PostgreSQL (`pgvector`) sorted by creation date, importance, or last recall.

* **Query Parameters**:
  * `limit` (integer, default: `20`, max: `200`)
  * `offset` (integer, default: `0`)
  * `sort_by` (string: `"created_at"` | `"importance_score"` | `"last_recalled_at"`)
* **Response (200 OK)**:
  ```json
  {
    "total": 42,
    "limit": 20,
    "offset": 0,
    "memories": [
      {
        "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
        "content": "User mentioned launching their weekend compiler project.",
        "importance_score": 0.85,
        "emotional_weight": 0.70,
        "valence": 0.40,
        "recall_count": 3,
        "last_recalled_at": "2026-08-28T14:30:00Z",
        "created_at": "2026-08-27T10:15:00Z",
        "wing": "episodic",
        "modality": "text"
      }
    ]
  }
  ```

---

## 3. Voice Management (`/api/voice`)

### `POST /api/voice/validate`
Uploads a WAV audio clip to validate duration (5–15s), sampling rate, signal-to-noise ratio, and runs automated Whisper transcription.

* **Form Data**: `file: UploadFile` (WAV, max 10MB)
* **Response (200 OK)**:
  ```json
  {
    "problems": [],
    "transcript": "Hello, this is my reference voice recording.",
    "duration_s": 8.04,
    "samplerate": 16000
  }
  ```

---

### `POST /api/voice/commit`
Saves an enrolled voice clip to `backend/voice_samples/` and configures `.env`.

* **Form Data**:
  * `file`: `UploadFile` (WAV)
  * `variant`: `"default"` | `"calm"` | `"warm"` | `"concerned"` | `"excited"`
  * `transcript`: `string`
  * `force`: `boolean` (optional overwrite guard)

---

## 4. Disaster Recovery & Portability (`/api/friend`)

### `POST /api/friend/export`
Packages all 4 state stores (Postgres 9 JSONL tables, Neo4j Cypher export, and SQLite cache) into a `.tar.gz` stream.

* **Query Parameters**: `skip_neo4j` (boolean, default `false`)
* **Response (200 OK)**: Streamed `application/gzip` download (`friend_export.tar.gz`).

---

### `POST /api/friend/import`
Restores an encrypted `.tar.gz` friend snapshot. Destructive operation requiring `force=true`.

* **Form Data**:
  * `file`: `UploadFile` (.tar.gz archive, max 100MB)
  * `force`: `boolean = true` (Mandatory safety guard)
  * `skip_neo4j`: `boolean = false`
