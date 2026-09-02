"""HUMANOID_ARCHITECTURE_RESEARCH.md Phase 0: which model a running agent
actually resolved, and from which `.env` file, used to require SSH-ing into
the host and reading `/proc/<pid>/environ` (see the ledger's 2026-09-02
entries) -- the exact "testing artifact, not a bad deploy" trap that cost a
whole verification pass. `BrainAgent` now logs `Config.LLM_PROVENANCE` at
construction so that answer is in the process's own log from the start.
"""

import logging

import pytest

from app import config as config_module
from app.agents.brain_agent import BrainAgent
from app.agents.subconscious_agent import SubconsciousAgent


def _provenance_records(caplog):
    return [
        record
        for record in caplog.records
        if "LLM config resolved from" in record.getMessage()
    ]


@pytest.mark.asyncio
async def test_construction_logs_the_resolved_llm_provenance(
    caplog, monkeypatch, mock_graph_db, mock_memory_store
):
    monkeypatch.setattr(
        config_module.config_instance, "LLM_CHAT_MODEL", "test-chat-model"
    )
    monkeypatch.setattr(
        config_module.config_instance, "LLM_FAST_MODEL", "test-fast-model"
    )
    monkeypatch.setattr(
        config_module.config_instance, "LLM_REFLECTION_MODEL", "test-reflection-model"
    )

    with caplog.at_level(logging.INFO, logger="app.agents.brain_agent"):
        BrainAgent(
            ollama_url="http://dummy",
            graph_db=mock_graph_db,
            memory_store=mock_memory_store,
        )

    records = _provenance_records(caplog)
    assert records, "expected one LLM provenance log line at construction"

    message = records[0].getMessage()
    assert str(config_module._env_file) in message
    assert "test-chat-model" in message
    assert "test-fast-model" in message
    assert "test-reflection-model" in message


@pytest.mark.asyncio
async def test_the_logged_provenance_names_the_real_env_file_path(
    caplog, mock_graph_db, mock_memory_store
):
    """Without a monkeypatch, this must name the one file `Config` actually
    reads -- not `backend/.env`, not `None` -- since that split is exactly
    what produced the ledger's stale-config incidents."""
    with caplog.at_level(logging.INFO, logger="app.agents.brain_agent"):
        BrainAgent(
            ollama_url="http://dummy",
            graph_db=mock_graph_db,
            memory_store=mock_memory_store,
        )

    records = _provenance_records(caplog)
    assert records
    assert str(config_module._env_file) in records[0].getMessage()


@pytest.mark.asyncio
async def test_subconscious_agent_construction_logs_llm_provenance(
    caplog, monkeypatch, mock_graph_db, mock_memory_store
):
    monkeypatch.setattr(
        config_module.config_instance, "LLM_CHAT_MODEL", "sub-chat-model"
    )
    monkeypatch.setattr(
        config_module.config_instance, "LLM_FAST_MODEL", "sub-fast-model"
    )
    monkeypatch.setattr(
        config_module.config_instance, "LLM_REFLECTION_MODEL", "sub-reflection-model"
    )

    with caplog.at_level(logging.INFO, logger="app.agents.subconscious_agent"):
        SubconsciousAgent(
            ollama_url="http://dummy",
            graph_db=mock_graph_db,
            memory_store=mock_memory_store,
        )

    records = [
        record
        for record in caplog.records
        if "[Subconscious] LLM config resolved from" in record.getMessage()
    ]
    assert records, "expected one LLM provenance log line from SubconsciousAgent"

    message = records[0].getMessage()
    assert str(config_module._env_file) in message
    assert "sub-chat-model" in message
    assert "sub-fast-model" in message
    assert "sub-reflection-model" in message
