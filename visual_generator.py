"""Phase 2: manual AI image generation.

Only a manual query starts this module. Each configured provider is independent;
one provider failing does not stop the others. No visual QA or licensing filter
is applied at this test stage.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

TIMEOUT = 60


def _clean_query(query: Any) -> str:
    return " ".join(str(query or "").split()).strip()[:1000]


def _image_bytes(value: Any) -> bytes | None:
    if isinstance(value, Image.Image):
        buffer = io.BytesIO()
        value.convert("RGB").save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()
    if isinstance(value, bytes):
        return value
    return None


def _valid_image(data: bytes) -> bool:
    if not data:
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _huggingface(query: str) -> dict[str, Any] | None:
    token = str(os.getenv("HF_TOKEN") or "").strip()
    if not token:
        return None
    from huggingface_hub import InferenceClient

    model = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    image = InferenceClient(api_key=token, provider="auto").text_to_image(query, model=model)
    data = _image_bytes(image)
    if not data or not _valid_image(data):
        return None
    return {
        "bytes": data,
        "hash": hashlib.sha256(data).hexdigest(),
        "source": "Hugging Face",
        "model": model,
    }


def _cloudflare(query: str) -> dict[str, Any] | None:
    account_id = str(os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    token = str(os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    if not account_id or not token:
        return None

    model = os.getenv(
        "CLOUDFLARE_IMAGE_MODEL",
        "@cf/black-forest-labs/flux-1-schnell",
    )
    response = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        json={"prompt": query},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    encoded = payload.get("result", {}).get("image") if isinstance(payload, dict) else None
    if not encoded:
        return None
    data = base64.b64decode(encoded)
    if not _valid_image(data):
        return None
    return {
        "bytes": data,
        "hash": hashlib.sha256(data).hexdigest(),
        "source": "Cloudflare Workers AI",
        "model": model,
    }


PROVIDERS = (
    ("Hugging Face", _huggingface),
    ("Cloudflare Workers AI", _cloudflare),
)


def generate_images(query: str) -> dict[str, Any]:
    q = _clean_query(query)
    if not q:
        return {"query": "", "assets": [], "providers": {}, "errors": {}}

    configured = []
    for name, provider in PROVIDERS:
        if name == "Hugging Face" and os.getenv("HF_TOKEN"):
            configured.append((name, provider))
        elif name == "Cloudflare Workers AI" and os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN"):
            configured.append((name, provider))

    def run(item):
        name, provider = item
        try:
            return name, provider(q), ""
        except Exception as exc:
            return name, None, f"{type(exc).__name__}: {exc}"

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=max(1, len(configured)), thread_name_prefix="ai-visual-provider") as executor:
        for name, asset, error in executor.map(run, configured):
            if asset:
                results[name] = asset
            if error:
                errors[name] = error

    assets = []
    seen = set()
    for name, _provider in configured:
        asset = results.get(name)
        if not asset or asset["hash"] in seen:
            continue
        seen.add(asset["hash"])
        assets.append(asset)

    return {
        "query": q,
        "assets": assets,
        "providers": {name: 1 if name in results else 0 for name, _ in configured},
        "errors": errors,
    }
