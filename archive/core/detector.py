import numpy as np
import logging
import pyaudio
from enum import Enum

# Configuration Constants
SAMPLE_RATE = 44100
CHUNK = 1024
CLAP_THRESHOLD = 7000  # Threshold for clap detection (device-dependent; tune as needed)
MIN_RMS = 800
MIN_CREST_FACTOR = 5.0
TRANSIENT_RATIO = 0.6
MAX_TRANSIENT_SAMPLES = 120
TRANSIENT_WINDOW_SAMPLES = 220
MIN_TRANSIENT_ENERGY_RATIO = 0.25


class SoundEvent(str, Enum):
    """Supported local sound events."""

    CLAP = "clap"
    DOUBLE_CLAP = "double_clap"


def _has_clap_transient(audio: np.ndarray) -> bool:
    """Checks whether the signal shape resembles a short clap-like transient."""
    abs_audio = np.abs(audio)
    peak_index = int(np.argmax(abs_audio))
    peak = float(abs_audio[peak_index])
    rms = float(np.sqrt(np.mean(np.square(audio))))

    if peak < CLAP_THRESHOLD or rms < MIN_RMS:
        return False

    crest_factor = peak / max(rms, 1.0)
    if crest_factor < MIN_CREST_FACTOR:
        return False

    transient_samples = int(np.sum(abs_audio >= peak * TRANSIENT_RATIO))
    if transient_samples > MAX_TRANSIENT_SAMPLES:
        return False

    start = max(0, peak_index - TRANSIENT_WINDOW_SAMPLES // 2)
    end = min(len(audio), peak_index + TRANSIENT_WINDOW_SAMPLES // 2)
    total_energy = float(np.sum(np.square(audio)))
    window_energy = float(np.sum(np.square(audio[start:end])))

    if total_energy <= 0:
        return False

    transient_energy_ratio = window_energy / total_energy
    return transient_energy_ratio >= MIN_TRANSIENT_ENERGY_RATIO


def detect_sound_event(data: bytes) -> SoundEvent | None:
    """Analyzes audio data and returns the detected sound event, if any."""
    try:
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if audio.size == 0:
            return None

        if _has_clap_transient(audio):
            return SoundEvent.CLAP

        return None
    except Exception as e:
        logging.error(f"Error during sound event detection: {e}")
        return None


class AudioStreamHandler:
    """Handles the PyAudio stream resource."""

    def __init__(self):
        self._p = None
        self._stream = None

    def initialize_stream(self) -> bool:
        """Initializes and opens the audio input stream."""
        try:
            self._p = pyaudio.PyAudio()
            self._stream = self._p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
            logging.info("Audio Stream Initialized.")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize audio stream: {e}")
            return False

    def read_data(self) -> bytes | None:
        """Reads a chunk of audio data."""
        if self._stream is None:
            logging.error("Stream not initialized.")
            return None
        try:
            return self._stream.read(CHUNK, exception_on_overflow=False)
        except IOError as e:
            logging.warning(f"IOError during stream read (Overflow): {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error during stream read: {e}")
            return None

    def close(self):
        """Closes and cleans up the audio resources."""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._p:
            self._p.terminate()
        logging.info("Audio Stream Closed.")
