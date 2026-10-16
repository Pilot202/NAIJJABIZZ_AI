"""Central configuration. Everything is read from environment variables (see .env.example).

Switch models without touching code:
  LLM_BACKEND=mock               -> no LLM, rule-based fallbacks only (works offline)
  LLM_BACKEND=openai_compatible  -> any OpenAI-compatible server (vLLM serving N-ATLaS-LLM,
                                    or a hosted API as backup). Set LLM_BASE_URL / LLM_MODEL.
"""
import os
from dataclasses import dataclass
from pathlib import Path

# Load .env file
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.split("#")[0].strip().strip('"').strip("'")
            if k:
                os.environ[k] = v


@dataclass(frozen=True)
class Settings:
    # Shared secret the backend must send in the X-API-Key header. Empty = auth disabled (dev only).
    api_key: str = os.getenv("ML_API_KEY", "")

    # Backend API (owned by the backend engineer)
    backend_base_url: str = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    backend_api_key: str = os.getenv("BACKEND_API_KEY", "")

    # LLM
    llm_backend: str = os.getenv("LLM_BACKEND", "mock")  # mock | openai_compatible
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "EMPTY")
    llm_model: str = os.getenv("LLM_MODEL", "NCAIR1/N-ATLaS")

    # Speech recognition
    asr_backend: str = os.getenv("ASR_BACKEND", "mock")  # mock | transformers | remote
    # N-ATLaS has one Whisper-Small speech model per language (all gated: accept the terms on each repo page).
    asr_model_en: str = os.getenv("ASR_MODEL_EN", "NCAIR1/NigerianAccentedEnglish")
    asr_model_yo: str = os.getenv("ASR_MODEL_YO", "NCAIR1/Yoruba-ASR")
    asr_model_ha: str = os.getenv("ASR_MODEL_HA", "NCAIR1/Hausa-ASR")
    asr_model_ig: str = os.getenv("ASR_MODEL_IG", "NCAIR1/Igbo-ASR")
    hf_token: str = os.getenv("HF_TOKEN", "")
    # ASR_BACKEND=remote: an OpenAI-style /v1/audio/transcriptions server (the Colab notebook, or a GPU box).
    # Both default to the LLM server's values, since the notebook serves the LLM and speech on one URL.
    asr_base_url: str = os.getenv("ASR_BASE_URL", "")
    asr_api_key: str = os.getenv("ASR_API_KEY", "")

    # Receipt OCR
    ocr_backend: str = os.getenv("OCR_BACKEND", "mock")  # mock | tesseract

    # Below this confidence the app should ask the merchant to repeat or edit before confirming.
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.6"))


settings = Settings()
