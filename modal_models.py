"""Download Hugging Face models into a persistent Modal Volume."""
import os

import modal

APP_NAME = "ml-service-model-cache"
VOLUME_NAME = os.getenv("MODAL_MODEL_VOLUME", "ml-service-models")
MOUNT_PATH = "/models"
HF_HOME = f"{MOUNT_PATH}/hf"
HF_HUB_CACHE = f"{HF_HOME}/hub"

DEFAULT_MODEL_REPOS = (
    "NCAIR1/NigerianAccentedEnglish",
    "NCAIR1/Yoruba-ASR",
    "NCAIR1/Hausa-ASR",
    "NCAIR1/Igbo-ASR",
    "NCAIR1/N-ATLaS",
)

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
download_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "huggingface_hub>=0.23"
)


@app.function(
    image=download_image,
    volumes={MOUNT_PATH: model_volume},
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=60 * 60,
    env={"HF_HOME": HF_HOME, "HF_HUB_CACHE": HF_HUB_CACHE},
)
def download_models(model_repos: str) -> list[str]:
    from huggingface_hub import snapshot_download

    downloaded = []
    for repo_id in (repo.strip() for repo in model_repos.split(",")):
        if not repo_id:
            continue
        snapshot_download(
            repo_id=repo_id,
            cache_dir=HF_HUB_CACHE,
            token=os.getenv("HF_TOKEN") or None,
        )
        model_volume.commit()
        downloaded.append(repo_id)
        print(f"Cached {repo_id} in Modal Volume {VOLUME_NAME}")
    return downloaded


@app.local_entrypoint()
def main(model_repos: str = ",".join(DEFAULT_MODEL_REPOS)) -> None:
    repos = download_models.remote(model_repos)
    print(f"Cached {len(repos)} model repositories in Volume {VOLUME_NAME}.")