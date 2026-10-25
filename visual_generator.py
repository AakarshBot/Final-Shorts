"""No-cost-first AI image generation shared by all Final-Shorts production lines.

AI Horde is the only provider enabled by default: it is volunteer-run and free.
Other hosted APIs can consume credits or incur charges, so they require an explicit
VISUAL_ALLOW_METERED_PROVIDERS=true opt-in even when credentials are configured.
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
AI_HORDE_DEFAULT_TIMEOUT = 300
AI_HORDE_MAX_TIMEOUT = 600
AI_HORDE_POLL_INTERVAL = 2.0
TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _env_enabled(name: str) -> bool:
    return str(os.getenv(name) or "").strip().casefold() in {"1", "true", "yes", "on"}


def _raise_for_status_or_transient(response, provider: str) -> None:
    status_code = getattr(response, "status_code", None)
    if status_code in TRANSIENT_HTTP_STATUSES:
        raise requests.HTTPError(
            f"{provider} temporarily returned HTTP {status_code}.",
            response=response,
        )
    response.raise_for_status()


def _cancel_horde_job(job_id: str, headers: dict[str, str]) -> None:
    """Best-effort cancellation so timed-out queue jobs do not run needlessly."""
    try:
        requests.delete(
            f"{AI_HORDE_URL}/generate/status/{quote(job_id, safe='')}",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException:
        pass


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


def _ai_horde(
    query: str,
    seed: int,
    *,
    width: int = 576,
    height: int = 1024,
) -> dict[str, Any] | None:
    """Generate one image through the free volunteer-run AI Horde queue.

    Anonymous requests are intentionally supported, but have the lowest queue
    priority. A free personal AI Horde API key can be supplied for better priority.
    """
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
            "width": int(width),
            "height": int(height),
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
    _raise_for_status_or_transient(response, "AI Horde")
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
    timeout = max(30, min(AI_HORDE_MAX_TIMEOUT, timeout))
    deadline = time.monotonic() + timeout
    last_progress: dict[str, Any] = {}
    consecutive_poll_errors = 0
    while time.monotonic() < deadline:
        time.sleep(min(AI_HORDE_POLL_INTERVAL, max(0.0, deadline - time.monotonic())))
        try:
            check = requests.get(
                f"{AI_HORDE_URL}/generate/check/{quote(job_id, safe='')}",
                headers=headers,
                timeout=15,
            )
            _raise_for_status_or_transient(check, "AI Horde status check")
            progress = check.json()
            if not isinstance(progress, dict):
                raise RuntimeError("AI Horde returned an invalid job status object.")
            last_progress = progress
            consecutive_poll_errors = 0
        except requests.RequestException:
            # A flaky status request must not discard an already accepted job.
            consecutive_poll_errors += 1
            if consecutive_poll_errors >= 8:
                raise RuntimeError(
                    "AI Horde status polling failed repeatedly. Check the network and retry; "
                    "the accepted job may still finish on the Horde."
                )
            continue
        except ValueError as exc:
            consecutive_poll_errors += 1
            if consecutive_poll_errors >= 3:
                raise RuntimeError("AI Horde repeatedly returned unreadable job status.") from exc
            continue
        if progress.get("faulted"):
            reason = progress.get("message") or progress.get("faulted") or "worker failed the job"
            raise RuntimeError(
                f"AI Horde worker could not complete the image job ({reason}). "
                "Retrying with a different prompt or free account key may help."
            )
        if progress.get("done"):
            break
    else:
        _cancel_horde_job(job_id, headers)
        wait = last_progress.get("wait_time")
        queue = last_progress.get("queue_position")
        queue_detail = []
        if queue is not None:
            queue_detail.append(f"queue position {queue}")
        if wait is not None:
            queue_detail.append(f"estimated wait {wait}s")
        queue_text = f" Last reported status: {', '.join(queue_detail)}." if queue_detail else ""
        if api_key == "0000000000":
            priority_hint = (
                " The anonymous key has the lowest queue priority; create a free account at "
                "https://stablehorde.net/ and set AI_HORDE_API_KEY to its API key to improve priority."
            )
        else:
            priority_hint = " Check AI Horde worker availability or increase AI_HORDE_TIMEOUT."
        raise TimeoutError(
            f"AI Horde's free queue did not finish within {timeout} seconds.{queue_text}{priority_hint}"
        )

    status = None
    last_status_error = None
    for attempt in range(3):
        try:
            status = requests.get(
                f"{AI_HORDE_URL}/generate/status/{quote(job_id, safe='')}",
                headers=headers,
                timeout=20,
            )
            _raise_for_status_or_transient(status, "AI Horde result download")
            break
        except requests.RequestException as exc:
            last_status_error = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    else:
        raise RuntimeError(f"AI Horde finished but result retrieval failed: {last_status_error}")
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
    asset = _make_asset(data, "AI Horde", str(generated.get("model") or "Community image model"))
    if not asset:
        raise RuntimeError("AI Horde returned bytes that were not a valid image.")
    return asset


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


def generate_images(query: str, *, orientation: str = "portrait") -> dict[str, Any]:
    """Generate images in strict no-cost mode by default.

    Args:
        query: User's prompt.
        orientation: "portrait" for Shorts/Top-5 (9:16), "landscape" for
            Long-form documentary scenes (16:9).
    """
    q = _clean_query(query)
    if not q:
        return {
            "query": "", "assets": [], "providers": {}, "errors": {},
            "message": "Enter an image prompt first.",
        }

    orientation = "landscape" if str(orientation).strip().casefold() == "landscape" else "portrait"
    width, height = (1024, 576) if orientation == "landscape" else (576, 1024)
    generation_seed = secrets.randbelow(2_147_483_647)
    configured = []
    allow_metered = _env_enabled("VISUAL_ALLOW_METERED_PROVIDERS")
    for name, provider in PROVIDERS:
        if name == "AI Horde":
            configured.append((name, provider))
        elif allow_metered and name == "Pollinations.ai" and (
            os.getenv("POLLINATIONS_API_KEY") or os.getenv("POLLINATIONS_API_TOKEN")
        ):
            configured.append((name, provider))
        elif allow_metered and name == "Hugging Face" and os.getenv("HF_TOKEN"):
            configured.append((name, provider))
        elif allow_metered and name == "Cloudflare Workers AI" and os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN"):
            configured.append((name, provider))

    def run(item):
        name, provider = item
        try:
            if name == "AI Horde":
                asset = provider(q, generation_seed, width=width, height=height)
            else:
                asset = provider(q, generation_seed)
            if not asset:
                return name, None, "Provider completed without returning a valid image."
            return name, asset, ""
        except Exception as exc:
            return name, None, f"{type(exc).__name__}: {exc}"

    results = {}
    errors = {}
    # Run only configured providers. The free AI Horde provider is the only
    # default, avoiding accidental spend from a token stored in the environment.
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
        message = "No free AI image provider returned a usable image."
        if detail:
            message += " " + detail
        if not allow_metered:
            message += (
                " Free mode is active; no metered provider was called. "
                "AI Horde is volunteer-run, so queue time can vary. For higher priority, "
                "set AI_HORDE_API_KEY to a free key from https://stablehorde.net/."
            )
    elif errors:
        message = "Some configured AI providers failed; successful images are still available."

    return {
        "query": q,
        "assets": assets,
        "providers": {name: 1 if name in results else 0 for name, _ in configured},
        "errors": errors,
        "message": message,
        "free_mode": not allow_metered,
        "orientation": orientation,
    }
