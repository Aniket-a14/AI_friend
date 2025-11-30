import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import AIBackend
from app.state_manager import AppState

class TestFullFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch all external dependencies
        self.patcher_config = patch('main.Config.validate')
        self.patcher_audio_stream = patch('main.AudioStream')
        self.patcher_audio_player = patch('main.AudioPlayer')
        self.patcher_wake_word = patch('main.WakeWordDetector')
        self.patcher_vad = patch('main.VAD')
        self.patcher_stt = patch('main.STTService')
        self.patcher_llm = patch('main.LLMService')
        self.patcher_tts = patch('main.TTSService')

        self.mock_config = self.patcher_config.start()
        self.mock_audio_stream_cls = self.patcher_audio_stream.start()
        self.mock_audio_player_cls = self.patcher_audio_player.start()
        self.mock_wake_word_cls = self.patcher_wake_word.start()
        self.mock_vad_cls = self.patcher_vad.start()
        self.mock_stt_cls = self.patcher_stt.start()
        self.mock_llm_cls = self.patcher_llm.start()
        self.mock_tts_cls = self.patcher_tts.start()

        # Setup instances
        self.mock_audio_stream = self.mock_audio_stream_cls.return_value
        self.mock_audio_player = self.mock_audio_player_cls.return_value
        self.mock_wake_word = self.mock_wake_word_cls.return_value
        self.mock_vad = self.mock_vad_cls.return_value
        self.mock_stt = self.mock_stt_cls.return_value
        self.mock_llm = self.mock_llm_cls.return_value
        self.mock_tts = self.mock_tts_cls.return_value

        # Configure mocks
        self.mock_stt.connect = AsyncMock()
        self.mock_stt.send_audio = AsyncMock()
        self.mock_stt.stop = AsyncMock()
        self.mock_stt.close = AsyncMock()
        self.mock_llm.generate_response = AsyncMock(return_value="Hello user")
        self.mock_tts.stream_audio = MagicMock(return_value=iter([b'audio']))
        
        # Mock STT receive to yield a result then wait
        async def mock_receive():
            yield "Hello AI", True
            # Keep yielding nothing or wait to simulate open connection
            # await asyncio.sleep(1) 
        
        self.mock_stt.receive = mock_receive

    async def asyncTearDown(self):
        self.patcher_config.stop()
        self.patcher_audio_stream.stop()
        self.patcher_audio_player.stop()
        self.patcher_wake_word.stop()
        self.patcher_vad.stop()
        self.patcher_stt.stop()
        self.patcher_llm.stop()
        self.patcher_tts.stop()

    async def test_wake_word_to_response(self):
        backend = AIBackend()
        
        # Scenario:
        # 1. Frame 1: Silence
        # 2. Frame 2: Wake Word Detected
        # 3. Frame 3: Speech (VAD True)
        # 4. Frame 4: Silence (VAD False) -> triggers STT result processing in loop
        # But STT result comes from stt_loop task.
        
        # We need to control the loop. 
        # We can let it run for a short time and then stop it.
        
        # Mock Audio Stream to return frames
        # We use side_effect to return frames and then None to simulate wait, 
        # but main loop waits for None. 
        # Let's return a few frames then raise KeyboardInterrupt to stop the loop cleanly? 
        # Or just set backend.running = False after some time.
        
        frames = [b'silence', b'wake', b'speech', b'silence']
        frame_iter = iter(frames)
        
        def get_frame_side_effect():
            try:
                return next(frame_iter)
            except StopIteration:
                return None
        
        self.mock_audio_stream.get_frame.side_effect = get_frame_side_effect
        
        # Mock Wake Word to detect on 2nd frame (b'wake')
        def wake_process(frame):
            return frame == b'wake'
        self.mock_wake_word.process.side_effect = wake_process
        
        # Mock VAD to detect speech on 3rd frame
        def vad_process(frame):
            return frame == b'speech'
        self.mock_vad.process.side_effect = vad_process

        # Run backend in a task
        run_task = asyncio.create_task(backend.run())
        
        # Wait for flow to happen
        await asyncio.sleep(0.5)
        
        # Verify Wake Word detected
        self.mock_wake_word.process.assert_called()
        # Verify STT connected
        self.mock_stt.connect.assert_called()
        
        # Verify STT received audio
        # self.mock_stt.send_audio.assert_called_with(b'speech') 
        # Note: send_audio is called when VAD is true AND state is ACTIVE_SESSION.
        # After wake word, state becomes ACTIVE_SESSION.
        # Next frame is b'speech', VAD is true -> send_audio called.
        
        # Verify LLM called (triggered by stt_loop receiving "Hello AI")
        self.mock_llm.generate_response.assert_called_with("Hello AI")
        
        # Verify TTS called
        self.mock_tts.stream_audio.assert_called_with("Hello user")
        
        # Verify Audio Player called
        self.mock_audio_player.play_stream.assert_called()
        
        # Stop backend
        backend.running = False
        await run_task

if __name__ == '__main__':
    unittest.main()
