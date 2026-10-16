"""Serve the FastAPI ML service on Modal using the persistent model cache."""
from pathlib import Path

import modal

APP_NAME = "ml-service-api"
VOLUME_NAME = "ml-service-models"
MOUNT_PATH = "/models"
HF_HOME = f"{MOUNT_PATH}/hf"
HF_HUB_CACHE = f"{HF_HOME}/hub"
ROOT = Path(__file__).resolve().parent

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name(VOLUME_NAME)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "tesseract-ocr")
    .pip_install_from_requirements(str(ROOT / "requirements-ml.txt"))
    .add_local_dir(str(ROOT / "app"), remote_path="/root/app")
)


@app.function(
    image=image,
    gpu="T4",
    volumes={MOUNT_PATH: model_volume},
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("ml-service-api"),
    ],
    env={
        "HF_HOME": HF_HOME,
        "HF_HUB_CACHE": HF_HUB_CACHE,
        "ASR_BACKEND": "transformers",
    },
    timeout=60 * 10,
)
@modal.asgi_app()
def fastapi_app():
    from app.main import app as web_app

    return web_app