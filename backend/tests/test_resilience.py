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
        
        mock_post.side_effect = [mock_cm_fail] * 5
        ollama_client.base_delay = 0.01
        
        res = await ollama_client.generate("Anyone there?")
        
        # Should return the default error string after 3 retries
        assert res == "Error generating response."
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_check_health_robustness(ollama_client):
    """Verify health check respects timeouts and handles failures."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_cm_timeout = MagicMock()
        mock_cm_timeout.__aenter__.side_effect = asyncio.TimeoutError()
        
        mock_get.side_effect = mock_cm_timeout
        
        is_healthy = await ollama_client.check_health()
        assert is_healthy is False
