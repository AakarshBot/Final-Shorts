"""Manual AI image generation for Final-Shorts.

AI Horde supplies the default no-cost, no-account provider. Optional Pollinations,
Hugging Face and Cloudflare providers are used only when their credentials exist.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image, UnidentifiedImageError


TIMEOUT = 60
AI_HORDE_URL = "https://aihorde.net/api/v2"
AI_HORDE_DEFAULT_TIMEOUT = 120


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


def _make_asset(data: bytes, source: str, model: str) -> dict[str, Any] | None:
    if not _valid_image(data):
        return None
    return {
        "bytes": data,
        "hash": hashlib.sha256(data).hexdigest(),
        "source": source,
        "model": model,
    }


def _ai_horde(query: str, seed: int) -> dict[str, Any] | None:
    """Generate one vertical image on the free volunteer-run AI Horde queue."""
    api_key = str(os.getenv("AI_HORDE_API_KEY") or "0000000000").strip()
    headers = {
        "apikey": api_key,
        "Client-Agent": "Final-Shorts:1.0:github.com/AakarshBot/Final-Shorts",
        "Content-Type": "application/json",
    }
    request_body = {
        "prompt": query,
        "params": {
            "sampler_name": "k_euler_a",
            "steps": 25,
            "cfg_scale": 7.0,
            "width": 576,
            "height": 1024,
            "n": 1,
            "seed": int(seed),
        },
        "nsfw": False,
        "censor_nsfw": True,
    }
    response = requests.post(
        f"{AI_HORDE_URL}/generate/async",
        json=request_body,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("AI Horde returned an unreadable submission response.") from exc
    job_id = str(payload.get("id") or "").strip()
    if not job_id:
        raise RuntimeError(
            "AI Horde accepted no image job. Response: "
            + str(payload.get("message") or payload.get("errors") or "no job id returned")
        )

    try:
        timeout = int(os.getenv("AI_HORDE_TIMEOUT", str(AI_HORDE_DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        timeout = AI_HORDE_DEFAULT_TIMEOUT
    timeout = max(20, min(240, timeout))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(3)
        check = requests.get(
            f"{AI_HORDE_URL}/generate/check/{quote(job_id, safe='')}",
            headers=headers,
            timeout=15,
        )
        check.raise_for_status()
        try:
            progress = check.json()
        except ValueError as exc:
            raise RuntimeError("AI Horde returned an unreadable job status.") from exc
        if progress.get("faulted"):
            raise RuntimeError(
                "AI Horde could not complete the image job. Try a shorter, more specific prompt."
            )
        if progress.get("done"):
            break
    else:
        raise TimeoutError(
            f"AI Horde's free queue did not finish within {timeout} seconds. "
            "The queue is volunteer-run; retry later or configure a personal provider token."
        )

    status = requests.get(
        f"{AI_HORDE_URL}/generate/status/{quote(job_id, safe='')}",
        headers=headers,
        timeout=20,
    )
    status.raise_for_status()
    try:
        complete = status.json()
    except ValueError as exc:
        raise RuntimeError("AI Horde returned an unreadable completed job.") from exc
    generations = complete.get("generations") or []
    if not generations:
        raise RuntimeError(
            "AI Horde finished the job but returned no image data. "
            "This can happen when the worker image expires or the queue is overloaded."
        )
    generated = generations[0]
    image_value = generated.get("img") or generated.get("image")
    if not image_value:
        raise RuntimeError("AI Horde completed the job without an image payload.")

    if isinstance(image_value, str) and image_value.startswith(("http://", "https://")):
        image_response = requests.get(image_value, timeout=TIMEOUT)
        image_response.raise_for_status()
        data = image_response.content
    elif isinstance(image_value, str):
        encoded = image_value.partition(",")[2] if image_value.startswith("data:") else image_value
        try:
            data = base64.b64decode(encoded, validate=False)
        except (ValueError, binascii.Error) as exc:
            raise RuntimeError("AI Horde returned image data that could not be decoded.") from exc
    elif isinstance(image_value, bytes):
        data = image_value
    else:
        raise RuntimeError("AI Horde returned an unsupported image payload.")
    return _make_asset(data, "AI Horde", str(generated.get("model") or "Community image model"))


def _pollinations(query: str, seed: int) -> dict[str, Any] | None:
    token = str(os.getenv("POLLINATIONS_API_KEY") or os.getenv("POLLINATIONS_API_TOKEN") or "").strip()
    if not token:
        return None
    model = os.getenv("POLLINATIONS_IMAGE_MODEL", "black-forest-labs/flux.1-schnell")
    response = requests.get(
        f"https://gen.pollinations.ai/image/{quote(query, safe='')}",
        params={
            "model": model,
            "width": 576,
            "height": 1024,
            "seed": seed,
            "nologo": "true",
            "private": "true",
        },
        headers={"Authorization": f"Bearer {token}", "Accept": "image/*"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    if "image/" not in str(response.headers.get("Content-Type") or "").casefold():
        raise RuntimeError("Pollinations returned a non-image response.")
    return _make_asset(response.content, "Pollinations.ai", model)


def _huggingface(query: str, seed: int) -> dict[str, Any] | None:
    token = str(os.getenv("HF_TOKEN") or "").strip()
    if not token:
        return None
    from huggingface_hub import InferenceClient

    model = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    image = InferenceClient(api_key=token, provider="auto").text_to_image(
        query,
        model=model,
        seed=seed,
    )
    data = _image_bytes(image)
    if not data:
        return None
    return _make_asset(data, "Hugging Face", model)


def _cloudflare(query: str, seed: int) -> dict[str, Any] | None:
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
        json={"prompt": query, "seed": seed},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    encoded = payload.get("result", {}).get("image") if isinstance(payload, dict) else None
    if not encoded:
        detail = payload.get("errors") if isinstance(payload, dict) else None
        raise RuntimeError(f"Cloudflare returned no image payload: {detail or 'empty result'}")
    try:
        data = base64.b64decode(encoded)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("Cloudflare returned image data that could not be decoded.") from exc
    return _make_asset(data, "Cloudflare Workers AI", model)


PROVIDERS = (
    ("AI Horde", _ai_horde),
    ("Pollinations.ai", _pollinations),
    ("Hugging Face", _huggingface),
    ("Cloudflare Workers AI", _cloudflare),
)


def generate_images(query: str) -> dict[str, Any]:
    q = _clean_query(query)
    if not q:
        return {"query": "", "assets": [], "providers": {}, "errors": {}, "message": "Enter an image prompt first."}

    generation_seed = secrets.randbelow(2_147_483_647)
    configured = []
    for name, provider in PROVIDERS:
        if name == "AI Horde":
            configured.append((name, provider))
        elif name == "Pollinations.ai" and (
            os.getenv("POLLINATIONS_API_KEY") or os.getenv("POLLINATIONS_API_TOKEN")
        ):
            configured.append((name, provider))
        elif name == "Hugging Face" and os.getenv("HF_TOKEN"):
            configured.append((name, provider))
        elif name == "Cloudflare Workers AI" and os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN"):
            configured.append((name, provider))

    def run(item):
        name, provider = item
        try:
            return name, provider(q, generation_seed), ""
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
        if not asset or asset.get("hash") in seen:
            continue
        seen.add(asset["hash"])
        assets.append(asset)

    message = ""
    if not assets:
        detail = " | ".join(f"{name}: {error}" for name, error in errors.items())
        message = "No AI image provider returned a usable image."
        if detail:
            message += " " + detail
    elif errors:
        message = "Some AI providers failed; successful images are still available."

    return {
        "query": q,
        "assets": assets,
        "providers": {name: 1 if name in results else 0 for name, _ in configured},
        "errors": errors,
        "message": message,
    }
