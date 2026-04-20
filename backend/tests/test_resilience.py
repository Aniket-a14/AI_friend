import pytest
import asyncio
import aiohttp
from unittest.mock import patch, MagicMock
from app.llm.ollama_client import OllamaClient

@pytest.fixture
def ollama_client():
    return OllamaClient(base_url="http://mock-ollama:11434")

@pytest.mark.asyncio
async def test_ollama_exponential_backoff_success(ollama_client):
    """
    Verify that OllamaClient retries on failure and succeeds if the service recovers.
    """
    # Simulate: 2 Fails (503), then 1 Success
    with patch("aiohttp.ClientSession.post") as mock_post:
        # Mocking the 503 response
        mock_503 = MagicMock()
        mock_503.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=503, message="Service Unavailable"
        )
        
        # Mocking the Success response
        mock_success = MagicMock()
        mock_success.status = 200
        mock_success.raise_for_status = MagicMock()
        async def mock_json(): return {"response": "Recovered!"}
        mock_success.json = mock_json

        # Setup sequence of responses
        # Note: We use a context manager for session.post so it returns a mock context manager
        mock_cm_503 = MagicMock()
        mock_cm_503.__aenter__.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=503, message="Busy"
        )
        
        mock_cm_success = MagicMock()
        mock_cm_success.__aenter__.return_value = mock_success
        
        # Return CM_503, CM_503, CM_SUCCESS
        mock_post.side_effect = [mock_cm_503, mock_cm_503, mock_cm_success]
        
        # Reduce delay for testing speed
        ollama_client.base_delay = 0.01 
        
        res = await ollama_client.generate("Hello?")
        
        assert res == "Recovered!"
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_ollama_backoff_exhaustion_fallback(ollama_client):
    """
    Verify that after 3 failed attempts, the client yields a fallback error message.
    """
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_cm_fail = MagicMock()
        mock_cm_fail.__aenter__.side_effect = aiohttp.ClientError("Perpetual Failure")
        
        # Each retry cycle now attempts both /api/generate and /api/chat.
        mock_post.side_effect = [mock_cm_fail] * 10
        ollama_client.base_delay = 0.01
        
        res = await ollama_client.generate("Anyone there?")
        
        # Should return the default error string after 3 retries
        assert res == "Error generating response."
        assert mock_post.call_count == 6

@pytest.mark.asyncio
async def test_check_health_robustness(ollama_client):
    """Verify health check respects timeouts and handles failures."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_cm_timeout = MagicMock()
        mock_cm_timeout.__aenter__.side_effect = asyncio.TimeoutError()
        
        mock_get.side_effect = mock_cm_timeout
        
        is_healthy = await ollama_client.check_health()
        assert is_healthy is False


@pytest.mark.asyncio
async def test_generate_falls_back_to_chat_endpoint(ollama_client):
    """If /api/generate returns 404, client should retry with /api/chat."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_not_found_resp = MagicMock()
        mock_not_found_resp.status = 404
        mock_not_found_resp.raise_for_status = MagicMock()

        async def _not_found_text():
            return '{"error":"not found"}'

        mock_not_found_resp.text = _not_found_text
        mock_not_found_cm = MagicMock()
        mock_not_found_cm.__aenter__.return_value = mock_not_found_resp

        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()

        async def _chat_json():
            return {"message": {"content": "Fallback chat response"}}

        mock_chat_resp.json = _chat_json
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_not_found_cm, mock_chat_cm]

        response = await ollama_client.generate("hello")

        assert response == "Fallback chat response"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_stream_falls_back_to_chat_endpoint(ollama_client):
    """If /api/generate stream returns 404, stream should continue via /api/chat."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_not_found_resp = MagicMock()
        mock_not_found_resp.status = 404
        mock_not_found_resp.raise_for_status = MagicMock()

        async def _not_found_text():
            return '{"error":"not found"}'

        mock_not_found_resp.text = _not_found_text
        mock_not_found_cm = MagicMock()
        mock_not_found_cm.__aenter__.return_value = mock_not_found_resp

        class AsyncBytesIterable:
            def __init__(self, items):
                self._items = items

            def __aiter__(self):
                async def _gen():
                    for item in self._items:
                        yield item

                return _gen()

        stream_lines = [
            b'{"message": {"content": "Hi "}, "done": false}\n',
            b'{"message": {"content": "there"}, "done": false}\n',
            b'{"done": true}\n',
        ]
        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()
        mock_chat_resp.content = AsyncBytesIterable(stream_lines)
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_not_found_cm, mock_chat_cm]

        chunks = []
        async for chunk in ollama_client.generate_stream("hello"):
            chunks.append(chunk)

        assert "".join(chunks) == "Hi there"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_falls_back_on_500_to_chat_endpoint(ollama_client):
    """If /api/generate returns 500, client should retry via /api/chat."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_error_resp = MagicMock()
        mock_error_resp.status = 500
        mock_error_resp.raise_for_status = MagicMock()

        async def _err_text():
            return '{"error":"temporary failure"}'

        mock_error_resp.text = _err_text
        mock_error_cm = MagicMock()
        mock_error_cm.__aenter__.return_value = mock_error_resp

        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()

        async def _chat_json():
            return {"message": {"content": "Recovered"}}

        mock_chat_resp.json = _chat_json
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_error_cm, mock_chat_cm]

        response = await ollama_client.generate("hello")

        assert response == "Recovered"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_stream_falls_back_on_500_to_chat_endpoint(ollama_client):
    """If /api/generate stream returns 500, stream should continue via /api/chat."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_error_resp = MagicMock()
        mock_error_resp.status = 500
        mock_error_resp.raise_for_status = MagicMock()

        async def _err_text():
            return '{"error":"temporary failure"}'

        mock_error_resp.text = _err_text
        mock_error_cm = MagicMock()
        mock_error_cm.__aenter__.return_value = mock_error_resp

        class AsyncBytesIterable:
            def __init__(self, items):
                self._items = items

            def __aiter__(self):
                async def _gen():
                    for item in self._items:
                        yield item

                return _gen()

        stream_lines = [
            b'{"message": {"content": "OK "}, "done": false}\n',
            b'{"message": {"content": "now"}, "done": false}\n',
            b'{"done": true}\n',
        ]
        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()
        mock_chat_resp.content = AsyncBytesIterable(stream_lines)
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_error_cm, mock_chat_cm]

        chunks = []
        async for chunk in ollama_client.generate_stream("hello"):
            chunks.append(chunk)

        assert "".join(chunks) == "OK now"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_falls_back_on_timeout_to_chat_endpoint(ollama_client):
    """If /api/generate times out, client should continue to /api/chat."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_timeout_cm = MagicMock()
        mock_timeout_cm.__aenter__.side_effect = asyncio.TimeoutError()

        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()

        async def _chat_json():
            return {"message": {"content": "Recovered after timeout"}}

        mock_chat_resp.json = _chat_json
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_timeout_cm, mock_chat_cm]

        response = await ollama_client.generate("hello")

        assert response == "Recovered after timeout"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_stream_falls_back_on_timeout_to_chat_endpoint(ollama_client):
    """If /api/generate stream times out, stream should continue via /api/chat."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_timeout_cm = MagicMock()
        mock_timeout_cm.__aenter__.side_effect = asyncio.TimeoutError()

        class AsyncBytesIterable:
            def __init__(self, items):
                self._items = items

            def __aiter__(self):
                async def _gen():
                    for item in self._items:
                        yield item

                return _gen()

        stream_lines = [
            b'{"message": {"content": "Hi "}, "done": false}\n',
            b'{"message": {"content": "there"}, "done": false}\n',
            b'{"done": true}\n',
        ]
        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()
        mock_chat_resp.content = AsyncBytesIterable(stream_lines)
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_timeout_cm, mock_chat_cm]

        chunks = []
        async for chunk in ollama_client.generate_stream("hello"):
            chunks.append(chunk)

        assert "".join(chunks) == "Hi there"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_stream_parses_fragmented_json_chunks(ollama_client):
    """Stream parser should recover when JSON objects are split across transport chunks."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_not_found_resp = MagicMock()
        mock_not_found_resp.status = 404
        mock_not_found_resp.raise_for_status = MagicMock()

        async def _not_found_text():
            return '{"error":"not found"}'

        mock_not_found_resp.text = _not_found_text
        mock_not_found_cm = MagicMock()
        mock_not_found_cm.__aenter__.return_value = mock_not_found_resp

        class AsyncBytesIterable:
            def __init__(self, items):
                self._items = items

            def __aiter__(self):
                async def _gen():
                    for item in self._items:
                        yield item

                return _gen()

        # First payload intentionally split across two chunks (no newline in first piece).
        stream_chunks = [
            b'{"message": {"content": "Hel',
            b'lo "}, "done": false}\n',
            b'{"message": {"content": "world"}, "done": false}\n',
            b'{"done": true}\n',
        ]
        mock_chat_resp = MagicMock()
        mock_chat_resp.status = 200
        mock_chat_resp.raise_for_status = MagicMock()
        mock_chat_resp.content = AsyncBytesIterable(stream_chunks)
        mock_chat_cm = MagicMock()
        mock_chat_cm.__aenter__.return_value = mock_chat_resp

        mock_post.side_effect = [mock_not_found_cm, mock_chat_cm]

        chunks = []
        async for chunk in ollama_client.generate_stream("hello"):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello world"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_generate_retries_with_latest_tag_for_untagged_model(ollama_client):
    """If an untagged model 404s, client should retry with :latest model variant."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_not_found_resp = MagicMock()
        mock_not_found_resp.status = 404
        mock_not_found_resp.raise_for_status = MagicMock()

        async def _not_found_text():
            return '{"error":"not found"}'

        mock_not_found_resp.text = _not_found_text
        mock_not_found_cm = MagicMock()
        mock_not_found_cm.__aenter__.return_value = mock_not_found_resp

        mock_latest_resp = MagicMock()
        mock_latest_resp.status = 200
        mock_latest_resp.raise_for_status = MagicMock()

        async def _latest_json():
            return {"message": {"content": "Recovered with latest tag"}}

        mock_latest_resp.json = _latest_json
        mock_latest_cm = MagicMock()
        mock_latest_cm.__aenter__.return_value = mock_latest_resp

        mock_post.side_effect = [mock_not_found_cm, mock_not_found_cm, mock_latest_cm]

        response = await ollama_client.generate("hello", model="llama3.2")

        assert response == "Recovered with latest tag"
        posted_models = [call.kwargs["json"]["model"] for call in mock_post.call_args_list]
        assert posted_models[:3] == ["llama3.2", "llama3.2", "llama3.2:latest"]
