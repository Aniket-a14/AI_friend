# Cloud LLM Fallback (Anthropic Claude)

For hardware environments that cannot comfortably host a 3B+ LLM locally, AI Friend provides an optional, provider-agnostic **Cloud LLM Fallback** adapter.

---

## Configuration

In your `.env` file, set:

```ini
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

---

## Endocrine Parameter Translation

Unlike simple LLM wrappers, the `AnthropicClient` adapter (`backend/app/llm/anthropic_client.py`) translates internal biological endocrine states into cloud API sampling parameters:

* `temperature` is modulated by Cortisol ($0.3 \leftrightarrow 0.9$).
* `top_p` is modulated by Dopamine ($0.6 \leftrightarrow 0.98$).
* `max_tokens` is bounded by Fatigue.
* System prompts carry the identical 3-Tier Persona boundary and friction directives.

---

## Privacy Notice

> [!WARNING]
> Setting `LLM_PROVIDER=anthropic` transmits conversation turns over HTTPS to Anthropic servers. This is an explicit opt-in choice for users who trade local containment for higher inference speed or model intelligence.
