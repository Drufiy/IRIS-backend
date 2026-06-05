"""TTS router — currently routes all output through ElevenLabs streaming."""

from loguru import logger
from voice.elevenlabs_tts import ElevenLabsTTS
from voice.stream_player import StreamPlayer


class TTSRouter:
    """
    Unified TTS interface consumed by IRISEventLoop.
    Routes speak() calls to ElevenLabsTTS.
    stop() propagates to the active TTS backend.
    """

    def __init__(self, config: dict) -> None:
        api_key  = config["elevenlabs_api_key"]
        voice_name = config.get("elevenlabs_voice_name", "Rachel")
        voice_id = config.get("elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
        model    = config.get("elevenlabs_model", "eleven_turbo_v2_5")
        base_url = config.get("elevenlabs_base_url")  # Optional: for shared backend mode

        self.voice_name = voice_name
        self._elevenlabs = ElevenLabsTTS(
            api_key=api_key,
            voice_id=voice_id,
            model=model,
            base_url=base_url,
        )
        self._player = StreamPlayer()
        self._active_backend = self._elevenlabs

    async def speak(self, text: str) -> None:
        """Speak text via the configured TTS backend."""
        if not text or not text.strip():
            return
        logger.info(
            "TTS speak with ElevenLabs voice {}: '{}{}'",
            self.voice_name,
            text[:80],
            "..." if len(text) > 80 else "",
        )
        try:
            await self._elevenlabs.speak(text)
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            # Don't re-raise — a TTS failure must never crash the event loop

    def stop(self) -> None:
        """Stop any in-progress TTS output immediately."""
        self._elevenlabs.stop()
        self._player.stop()
        logger.debug("TTSRouter stopped")
