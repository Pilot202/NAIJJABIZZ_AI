"""Audio helpers. Whisper-style models expect 16 kHz mono WAV; phones upload m4a/webm/ogg/mp3."""
import subprocess
import tempfile
from pathlib import Path


def to_wav_16k_mono(audio_bytes: bytes, suffix: str = ".m4a") -> bytes:
    """Convert any ffmpeg-readable audio to 16 kHz mono WAV. Requires the ffmpeg binary."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"in{suffix}"
        dst = Path(tmp) / "out.wav"
        src.write_bytes(audio_bytes)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise ValueError(f"ffmpeg could not read the audio: {proc.stderr.decode(errors='ignore')[-300:]}")
        return dst.read_bytes()
