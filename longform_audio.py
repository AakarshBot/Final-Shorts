"""Long-form Chatterbox narration, sharing the Shorts model and voice cache."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from audio import (
    _chatterbox_audio_texts,
    _chatterbox_delivery,
    _file_sha256,
    _prepare_chatterbox_reference,
    get_chatterbox_model,
    synthesize_linear_timings,
)

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_REFERENCE = Path(os.getenv("AUDIO_REFERENCE", ROOT_DIR / "audio_reference.wav"))
LONGFORM_OUTPUT_DIR = ROOT_DIR / "output" / "audio_longform"
ACT_PAUSE_SECONDS = 0.80
SCENE_PAUSE_SECONDS = 0.15


def _clean(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _scene_starts(scenes: list[dict[str, Any]], durations: list[float]) -> list[float]:
    starts = []
    elapsed = 0.0
    for index, (scene, duration) in enumerate(zip(scenes, durations)):
        starts.append(round(elapsed, 3))
        if index < len(scenes) - 1:
            next_act = scenes[index + 1].get("act_number")
            curr_act = scene.get("act_number")
            gap = ACT_PAUSE_SECONDS if next_act and curr_act and next_act != curr_act else SCENE_PAUSE_SECONDS
            elapsed += duration + gap
    return starts


def _result(
    scenes: list[dict[str, Any]],
    texts: list[str],
    audio_texts: list[str],
    durations: list[float],
    target_dir: Path,
    total_duration: float,
    reference: Path | None,
    run_number: int,
    from_cache: bool,
) -> dict[str, Any]:
    scene_paths = []
    scene_timings = []
    starts = _scene_starts(scenes, durations)
    for index, (scene, text, duration, start_seconds) in enumerate(
        zip(scenes, texts, durations, starts), 1
    ):
        scene_path = target_dir / f"scene_{index:02d}.wav"
        scene_paths.append(str(scene_path))
        scene_timings.append(
            {
                "scene": index,
                "act": scene.get("act_number", 1),
                "path": str(scene_path),
                "duration": round(duration, 3),
                "start_seconds": start_seconds,
                "timings": synthesize_linear_timings(text, duration),
                "from_cache": from_cache,
            }
        )
    return {
        "master_path": str(target_dir / "longform_master.wav"),
        "scene_paths": scene_paths,
        "scene_durations": durations,
        "scenes": scene_timings,
        "total_duration": round(total_duration, 2),
        "engine": "Chatterbox-Turbo",
        "reference": str(reference) if reference else "Built-in Chatterbox neural voice",
        "run_number": run_number,
        "delivery": "Script-led",
        "from_cache": from_cache,
    }


class LongformAudioEngine:
    """Synthesizes long-form narration, caching exact outputs between Streamlit reruns."""

    @classmethod
    def generate(
        cls,
        script_data: dict[str, Any],
        run_number: int = 1,
        reference_audio: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        language = str(
            script_data.get("language_used") or script_data.get("language") or "english"
        ).strip().casefold()
        if language not in {"english", "en"}:
            raise ValueError("Long-form Chatterbox Turbo currently supports English narration only.")

        scenes = list(script_data.get("scenes") or [])
        if not scenes:
            raise ValueError("The approved Long-form script contains no scenes.")

        texts = [_clean(scene.get("voiceover")) for scene in scenes]
        for number, text in enumerate(texts, 1):
            if not text:
                raise ValueError(f"Scene {number} has no voiceover narration.")

        if reference_audio is not None:
            actual_ref = Path(reference_audio)
            if not actual_ref.is_file():
                raise FileNotFoundError(f"Chatterbox reference file is missing: {actual_ref}")
        else:
            actual_ref = DEFAULT_REFERENCE if DEFAULT_REFERENCE.is_file() else None

        reference_fingerprint = None
        if actual_ref:
            reference_fingerprint = {
                "path": str(actual_ref.resolve()),
                "sha256": _file_sha256(actual_ref),
            }

        audio_texts = _chatterbox_audio_texts(texts)
        temperatures = []
        for number, (scene, text) in enumerate(zip(scenes, texts), 1):
            temperature = _chatterbox_delivery(text, number, len(texts))[1]
            act_num = scene.get("act_number", 1)
            # Keep the established act shape, unless the script calls for serious or high-energy delivery.
            if temperature > 0.72:
                if act_num == 1:
                    temperature = max(temperature, 0.84)
                elif act_num == 5:
                    temperature = max(temperature, 0.85)
                elif act_num == 6 and number == len(texts):
                    temperature = max(temperature, 0.82)
            temperatures.append(round(temperature, 3))

        signature_payload = {
            "cache_version": "longform-chatterbox-v2-script-led",
            "texts": texts,
            "audio_texts": audio_texts,
            "temperatures": temperatures,
            "acts": [scene.get("act_number", 1) for scene in scenes],
            "run_number": int(run_number),
            "reference": reference_fingerprint,
            "act_pause_seconds": ACT_PAUSE_SECONDS,
            "scene_pause_seconds": SCENE_PAUSE_SECONDS,
        }
        signature = hashlib.sha256(
            json.dumps(signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        text_key = hashlib.sha1(" ".join(texts).encode("utf-8")).hexdigest()[:12]
        output_base = Path(output_dir) if output_dir else LONGFORM_OUTPUT_DIR / text_key
        target_dir = output_base / f".chatterbox_{signature[:20]}"
        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = target_dir / ".longform_manifest.json"
        manifest = None

        # Check exact outputs before importing torch or loading the model.
        try:
            candidate = json.loads(manifest_path.read_text(encoding="utf-8"))
            durations = candidate.get("scene_durations")
            required_paths = [target_dir / "longform_master.wav"] + [
                target_dir / f"scene_{index:02d}.wav" for index in range(1, len(scenes) + 1)
            ]
            if (
                candidate.get("signature") == signature
                and isinstance(durations, list)
                and len(durations) == len(scenes)
                and all(float(value) > 0 for value in durations)
                and float(candidate.get("total_duration", 0)) > 0
                and all(path.is_file() and path.stat().st_size > 1000 for path in required_paths)
            ):
                manifest = candidate
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            manifest = None

        if manifest is not None:
            return _result(
                scenes,
                texts,
                audio_texts,
                [float(value) for value in manifest["scene_durations"]],
                target_dir,
                float(manifest["total_duration"]),
                actual_ref,
                run_number,
                from_cache=True,
            )

        import torch
        import torchaudio

        model = get_chatterbox_model()
        _prepare_chatterbox_reference(model, actual_ref, reference_fingerprint)

        for old in target_dir.glob("*.wav"):
            try:
                old.unlink()
            except OSError:
                pass
        manifest_path.unlink(missing_ok=True)

        waves = []
        scene_durations = []
        for number, (scene, text) in enumerate(zip(scenes, audio_texts), 1):
            torch.manual_seed(run_number * 1000 + number)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(run_number * 1000 + number)

            wav = model.generate(text, temperature=temperatures[number - 1])
            wav = wav.detach().cpu()
            if wav.ndim == 1:
                wav = wav.unsqueeze(0)
            waves.append(wav)
            duration = wav.shape[-1] / model.sr
            scene_durations.append(duration)
            torchaudio.save(str(target_dir / f"scene_{number:02d}.wav"), wav, model.sr)

        act_pause_samples = int(model.sr * ACT_PAUSE_SECONDS)
        scene_pause_samples = int(model.sr * SCENE_PAUSE_SECONDS)
        act_silence = torch.zeros((1, act_pause_samples))
        scene_silence = torch.zeros((1, scene_pause_samples))
        combined = []
        for index, (wav, scene) in enumerate(zip(waves, scenes)):
            combined.append(wav)
            if index < len(waves) - 1:
                next_act = scenes[index + 1].get("act_number")
                curr_act = scene.get("act_number")
                if next_act and curr_act and next_act != curr_act:
                    combined.append(act_silence)
                else:
                    combined.append(scene_silence)

        full_wave = torch.cat(combined, dim=-1)
        peak = full_wave.abs().max()
        if peak.item() > 0:
            full_wave = full_wave * (0.94 / peak)
        master_path = target_dir / "longform_master.wav"
        torchaudio.save(str(master_path), full_wave, model.sr)
        total_duration = full_wave.shape[-1] / model.sr

        manifest = {
            "signature": signature,
            "scene_durations": [round(value, 6) for value in scene_durations],
            "total_duration": round(total_duration, 6),
        }
        fd, raw_manifest = tempfile.mkstemp(
            prefix=".longform_manifest_", suffix=".json.tmp", dir=target_dir
        )
        os.close(fd)
        temp_path = Path(raw_manifest)
        try:
            temp_path.write_text(json.dumps(manifest), encoding="utf-8")
            temp_path.replace(manifest_path)
        finally:
            temp_path.unlink(missing_ok=True)

        return _result(
            scenes,
            texts,
            audio_texts,
            scene_durations,
            target_dir,
            total_duration,
            actual_ref,
            run_number,
            from_cache=False,
        )

    @classmethod
    def approve_audio(cls, audio_data: dict[str, Any]) -> dict[str, Any]:
        """Validates and marks generated Long-form audio as approved."""
        if not isinstance(audio_data, dict):
            raise ValueError("Invalid audio data.")
        master_path = Path(audio_data.get("master_path", ""))
        if not master_path.is_file() or master_path.stat().st_size <= 1000:
            raise ValueError("Master audio file is missing or invalid.")
        approved = dict(audio_data)
        approved["approved_for_assembly"] = True
        return approved


__all__ = ["LongformAudioEngine", "get_chatterbox_model"]
