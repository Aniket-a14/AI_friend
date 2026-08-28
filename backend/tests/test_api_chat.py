"""`app/api/chat.py` (roadmap Phase 5.2) is the web UI's only text path onto
the real cognitive pipeline -- a WebSocket that publishes `chat.input` and
fans out `chat.output` to every connected browser tab from one shared
JetStream subscription.

Two things this suite exists to pin down:

1. The app-wide `require_lan_client`/`require_session_auth` dependencies were
   retyped from `Request` to `HTTPConnection` specifically so they would
   apply to this WebSocket route at all -- a `Request`-typed dependency
   raises `TypeError` on every WebSocket connection attempt rather than
   enforcing the policy, silently exempting the socket instead of gating it.
2. `ChatBridge` holds one durable JetStream consumer for the process, not one
   per connection (`BaseAgent.subscribe` has no ephemeral mode), so two
   connections attached to the same broadcast must each see every message,
   and a closed connection must not leak its queue in `_listeners` forever.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse

from app.api.chat import bridge as chat_bridge
from app.contracts import ChatOutput
from main import app

WS_PATH = "/api/chat/ws"
AUTH_QS = "?key=test-key"


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module.config_instance, "LAN_ONLY", False)
    monkeypatch.setattr(config_module.config_instance, "BACKEND_ACCESS_KEY", "test-key")


@pytest.fixture(autouse=True)
def _reset_bridge():
    """The bridge is a process-wide singleton (one JetStream consumer for
    every browser tab) -- reset its per-test state so a queue attached or a
    connection opened in one test can't leak into the next."""
    chat_bridge._listeners.clear()
    chat_bridge._started = False
    chat_bridge.nc = None
    chat_bridge.js = None
    yield
    chat_bridge._listeners.clear()
    chat_bridge._started = False
    chat_bridge.nc = None
    chat_bridge.js = None


@pytest.fixture
def client():
    return TestClient(app)


def test_rejects_a_connection_with_no_key_configured_and_missing(client, monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module.config_instance, "BACKEND_ACCESS_KEY", None)
    with pytest.raises(WebSocketDenialResponse):
        with client.websocket_connect(WS_PATH):
            pass


def test_rejects_a_connection_with_the_wrong_key(client):
    with pytest.raises(WebSocketDenialResponse):
        with client.websocket_connect(f"{WS_PATH}?key=wrong"):
            pass


def test_accepts_a_connection_with_the_correct_key(client):
    with client.websocket_connect(f"{WS_PATH}{AUTH_QS}"):
        pass  # connecting and closing cleanly is the assertion


def test_sending_text_publishes_a_chat_input_with_a_turn_id(client):
    published = []

    async def _fake_publish(subject, data, **kwargs):
        published.append((subject, data))

    chat_bridge.publish = _fake_publish  # bypass BaseAgent/NATS entirely
    with client.websocket_connect(f"{WS_PATH}{AUTH_QS}") as ws:
        ws.send_text("hello friend")
        import time

        time.sleep(0.05)  # let the server-side receive loop run

    assert len(published) == 1
    subject, data = published[0]
    assert subject.value == "chat.input"
    assert data["text"] == "hello friend"
    assert data["turn_id"]  # a real turn id was minted, not left blank


def test_blank_messages_are_not_published(client):
    published = []

    async def _fake_publish(subject, data, **kwargs):
        published.append((subject, data))

    chat_bridge.publish = _fake_publish
    with client.websocket_connect(f"{WS_PATH}{AUTH_QS}") as ws:
        ws.send_text("   ")
        import time

        time.sleep(0.05)

    assert published == []


def test_a_chat_output_message_is_forwarded_to_the_connected_socket(client):
    with client.websocket_connect(f"{WS_PATH}{AUTH_QS}") as ws:
        # Nothing calls the mesh here -- simulate what BaseAgent.subscribe's
        # handler would do on a real chat.output delivery.
        import asyncio

        asyncio.run(
            chat_bridge._on_chat_output(
                ChatOutput(content="hi there", turn_id="t1").model_dump()
            )
        )
        received = ws.receive_json()

    assert received["content"] == "hi there"
    assert received["turn_id"] == "t1"


def test_two_connections_both_receive_the_same_broadcast(client):
    import asyncio

    with client.websocket_connect(f"{WS_PATH}{AUTH_QS}") as ws1:
        with client.websocket_connect(f"{WS_PATH}{AUTH_QS}") as ws2:
            asyncio.run(
                chat_bridge._on_chat_output(
                    ChatOutput(content="broadcast", turn_id="t2").model_dump()
                )
            )
            assert ws1.receive_json()["content"] == "broadcast"
            assert ws2.receive_json()["content"] == "broadcast"


def test_closing_a_connection_detaches_its_listener_queue(client):
    assert len(chat_bridge._listeners) == 0
    with client.websocket_connect(f"{WS_PATH}{AUTH_QS}"):
        assert len(chat_bridge._listeners) == 1
    assert len(chat_bridge._listeners) == 0
