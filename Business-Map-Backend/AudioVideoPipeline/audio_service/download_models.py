"""
download_models.py
===================
Downloads every model the audio service needs into a portable folder
structure under the repo (`models/` by default). Used two ways:

1. STANDALONE (pre-warm the cache before your first real run, optional):
       python download_models.py
   Downloads everything into <repo>/models/ (or LOCAL_MODEL_CACHE_DIR if
   set). You can then copy that `models/` folder to another machine, or
   point PERSISTENT_MODELS_DIR at a shared copy of it to skip downloading
   on a second machine.

2. IMPORTED (this is what makes `python run_backend.py` alone work end
   to end on a fresh clone, with no manual step): pipeline_v3_1_production.py
   imports download_whisper and calls it directly with
   LOCAL_MODEL_CACHE_DIR as the destination whenever a model isn't
   already present locally or in PERSISTENT_MODELS_DIR. This means the
   very first `python run_backend.py` run on a brand new clone downloads
   models automatically into the same `models/` folder this script would
   produce — no extra steps needed.
"""

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = Path(os.environ.get("LOCAL_MODEL_CACHE_DIR", str(_REPO_ROOT / "models")))


def download_whisper(dest: Path = None, whisper_name: str = "large-v3"):
    from huggingface_hub import snapshot_download

    dest = Path(dest) if dest else (MODEL_DIR / f"whisper-{whisper_name}")
    if dest.exists() and any(dest.iterdir()):
        print(f"[skip] {dest} already populated")
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    repo_id = f"Systran/faster-whisper-{whisper_name}"
    print(f"[download] {repo_id} (ctranslate2 format)...")
    snapshot_download(repo_id=repo_id, local_dir=str(dest), local_dir_use_symlinks=False)
    print(f"[ok] saved to {dest}")
    return dest


def download_qwen(dest: Path = None, model_id: str = "Qwen/Qwen3-VL-2B-Instruct"):
    """
    Downloads the Qwen3-VL vision-language model (used by video_service)
    into the same portable models/ folder as the audio models, instead of
    the default Hugging Face cache (~/.cache/huggingface/hub). Kept here
    alongside the other downloaders so every model in the pipeline is
    fetched and cached the same, consistent way.
    """
    from huggingface_hub import snapshot_download

    dest = Path(dest) if dest else (MODEL_DIR / model_id.split("/")[-1])
    if dest.exists() and any(dest.iterdir()):
        print(f"[skip] {dest} already populated")
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[download] {model_id} (transformers)...")
    snapshot_download(repo_id=model_id, local_dir=str(dest), local_dir_use_symlinks=False)
    print(f"[ok] saved to {dest}")
    return dest


if __name__ == "__main__":
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    download_whisper()
    download_qwen()
    print("\nAll models downloaded to:", MODEL_DIR)
    print("The audio service will reuse this folder automatically on future runs.")