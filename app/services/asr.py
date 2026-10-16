"""Speech recognition wrapper (N-ATLaS ASR: one Whisper-Small model per language, 16 kHz, max 30 s per clip).

ASR_BACKEND=mock         -> returns a fixed demo phrase so the rest of the pipeline can be built first.
ASR_BACKEND=transformers -> loads the language's NCAIR1 model in this process (lazy, cached).
ASR_BACKEND=remote       -> sends the audio to an OpenAI-style /v1/audio/transcriptions server, such as the
                            Colab notebook's section 5 server or a GPU box. Uses ASR_BASE_URL / ASR_API_KEY,
                            falling back to LLM_BASE_URL / LLM_API_KEY.

The caller chooses the language (the merchant's language picker), so no language detection is needed.
Errors the merchant can act on (clip too long, unreadable audio, server down) are raised as ValueError,
which the routers turn into HTTP 400.
"""
import io
from typing import Dict, Optional, Tuple

import httpx

from app.config import settings
from app.schemas import Language
from app.utils.audio import to_wav_16k_mono

MAX_SECONDS = 30  # the models accept at most 30 s per inference

_pipelines: Dict[Language, object] = {}

_MOCK_PHRASE = "I just bought 50 bags of rice for 4 million naira"


def _model_id(language: Language) -> str:
    return {
        Language.en: settings.asr_model_en,
        Language.yo: settings.asr_model_yo,
        Language.ha: settings.asr_model_ha,
        Language.ig: settings.asr_model_ig,
    }[language]


def _get_pipeline(language: Language):
    if language not in _pipelines:
        from transformers import pipeline  # heavy import, only when needed

        _pipelines[language] = pipeline(
            "automatic-speech-recognition",
            model=_model_id(language),
            token=settings.hf_token or None,
        )
    return _pipelines[language]


def _remote_endpoint() -> str:
    url = (settings.asr_base_url or settings.llm_base_url).rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return f"{url}/audio/transcriptions"


def _transcribe_remote(audio_bytes: bytes, language: Language, filename: str) -> Tuple[str, Optional[float]]:
    endpoint = _remote_endpoint()
    headers = {}
    api_key = settings.asr_api_key or settings.llm_api_key
    if api_key and api_key != "EMPTY":
        headers["Authorization"] = f"Bearer {api_key}"

    files = {"file": (filename or "audio.m4a", audio_bytes)}
    # `language` picks the model on our server; `model` is there for other OpenAI-style servers.
    data = {"language": language.value, "model": _model_id(language)}
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(endpoint, files=files, data=data, headers=headers)
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not reach the speech server at {endpoint}: {exc}") from exc

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ValueError(f"Speech server returned {resp.status_code}: {detail}")
    return resp.json().get("text", "").strip(), None


def transcribe(audio_bytes: bytes, language: Language, filename: str = "audio.m4a") -> Tuple[str, Optional[float]]:
    """Return (transcript, confidence or None)."""
    if settings.asr_backend == "mock":
        return _MOCK_PHRASE, None

    if settings.asr_backend == "remote":
        return _transcribe_remote(audio_bytes, language, filename)

    suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".m4a"
    wav = to_wav_16k_mono(audio_bytes, suffix=suffix)

    import soundfile as sf  # installed via requirements-ml.txt

    audio, sr = sf.read(io.BytesIO(wav))
    if len(audio) / sr > MAX_SECONDS:
        raise ValueError(f"Audio is longer than {MAX_SECONDS} seconds. Ask the merchant to say it in a shorter clip.")
    result = _get_pipeline(language)({"array": audio, "sampling_rate": sr})
    return result["text"].strip(), None
