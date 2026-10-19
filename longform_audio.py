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
    _file_sha256,
    _generate_chatterbox_take,
    _normalise_chatterbox_model_version,
    _prepare_chatterbox_reference,
    _split_waveform_by_text,
    get_chatterbox_model,
    synthesize_linear_timings,
)

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_REFERENCE = Path(os.getenv("AUDIO_REFERENCE", ROOT_DIR / "audio_reference.wav"))
LONGFORM_OUTPUT_DIR = ROOT_DIR / "output" / "audio_longform"
ACT_PAUSE_SECONDS = 0.80
CHUNK_PAUSE_SECONDS = 0.08
MAX_CHUNK_WORDS = 100
MAX_CHUNK_CHARACTERS = 900


def _clean(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _scene_starts(
    scenes: list[dict[str, Any]],
    durations: list[float],
    chunk_ids: list[int],
) -> list[float]:
    """Use gaps only at actual generated-chunk and documentary-act boundaries."""
    starts = []
    elapsed = 0.0
    for index, (scene, duration) in enumerate(zip(scenes, durations)):
        starts.append(round(elapsed, 3))
        elapsed += duration
        if index < len(scenes) - 1:
            next_act = scenes[index + 1].get("act_number")
            curr_act = scene.get("act_number")
            if next_act and curr_act and next_act != curr_act:
                elapsed += ACT_PAUSE_SECONDS
            elif chunk_ids[index] != chunk_ids[index + 1]:
                elapsed += CHUNK_PAUSE_SECONDS
    return starts


def _audio_chunk_ranges(
    scenes: list[dict[str, Any]],
    texts: list[str],
    max_words: int = MAX_CHUNK_WORDS,
    max_characters: int = MAX_CHUNK_CHARACTERS,
) -> list[tuple[int, int]]:
    """Group several narration scenes into one TTS request while respecting model context."""
    chunks: list[tuple[int, int]] = []
    start = 0
    current_words = 0
    current_characters = 0
    current_act = scenes[0].get("act_number", 1)

    for index, (scene, text) in enumerate(zip(scenes, texts)):
        act = scene.get("act_number", 1)
        words = len(text.split())
        characters = len(text)
        should_break = index > start and (
            act != current_act
            or current_words + words > max_words
            or current_characters + characters > max_characters
        )
        if should_break:
            chunks.append((start, index))
            start = index
            current_words = 0
            current_characters = 0
            current_act = act
        current_words += words
        current_characters += characters

    chunks.append((start, len(texts)))
    return chunks


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
    chunk_ids: list[int],
    model_version: str,
) -> dict[str, Any]:
    scene_paths = []
    scene_timings = []
    starts = _scene_starts(scenes, durations, chunk_ids)
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
        "engine": "Chatterbox-Full" if model_version == "full" else "Chatterbox-Turbo",
        "model_version": model_version,
        "continuous_audio": True,
        "reference": str(reference) if reference else "Built-in Chatterbox neural voice",
        "run_number": run_number,
        "delivery": "Continuous narration grouped by paragraph-sized chunks",
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
        model_version: str = "turbo",
    ) -> dict[str, Any]:
        """Synthesize long-form narration in grouped chunks, never one request per scene."""
        language = str(
            script_data.get("language_used") or script_data.get("language") or "english"
        ).strip().casefold()
        if language not in {"english", "en"}:
            raise ValueError("Chatterbox Full and Turbo currently support English narration only.")

        scenes = list(script_data.get("scenes") or [])
        if not scenes:
            raise ValueError("The approved Long-form script contains no scenes.")

        texts = [_clean(scene.get("voiceover")) for scene in scenes]
        for number, text in enumerate(texts, 1):
            if not text:
                raise ValueError(f"Scene {number} has no voiceover narration.")

        selected_model = _normalise_chatterbox_model_version(model_version)
        chunk_ranges = _audio_chunk_ranges(scenes, texts)
        chunk_ids = [0] * len(scenes)
        for chunk_number, (start, end) in enumerate(chunk_ranges):
            for scene_index in range(start, end):
                chunk_ids[scene_index] = chunk_number

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
        settings = (
            {"temperature": 0.75, "cfg_weight": 0.35, "exaggeration": 0.35,
             "min_p": 0.05, "top_p": 1.0, "repetition_penalty": 1.2}
            if selected_model == "full"
            else {"temperature": 0.80}
        )
        signature_payload = {
            "cache_version": "longform-chatterbox-grouped-continuous-v4",
            "model_version": selected_model,
            "texts": texts,
            "audio_texts": audio_texts,
            "chunk_ranges": chunk_ranges,
            "settings": settings,
            "run_number": int(run_number),
            "reference": reference_fingerprint,
            "act_pause_seconds": ACT_PAUSE_SECONDS,
            "chunk_pause_seconds": CHUNK_PAUSE_SECONDS,
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
                and candidate.get("model_version") == selected_model
                and candidate.get("chunk_ids") == chunk_ids
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
                chunk_ids=chunk_ids,
                model_version=selected_model,
            )

        import torch
        import torchaudio

        model = get_chatterbox_model() if selected_model == "turbo" else get_chatterbox_model("full")
        _prepare_chatterbox_reference(model, actual_ref, reference_fingerprint)

        for old in target_dir.glob("*.wav"):
            try:
                old.unlink()
            except OSError:
                pass
        manifest_path.unlink(missing_ok=True)

        generated_chunks = []
        for chunk_number, (start, end) in enumerate(chunk_ranges, 1):
            chunk_text = " ".join(audio_texts[start:end])
            wav = _generate_chatterbox_take(
                model,
                chunk_text,
                selected_model,
                seed=run_number * 1000 + chunk_number,
            )
            generated_chunks.append((start, end, wav))

        combined = []
        for chunk_index, (start, end, wav) in enumerate(generated_chunks):
            combined.append(wav)
            if chunk_index < len(generated_chunks) - 1:
                next_start, _next_end, _next_wav = generated_chunks[chunk_index + 1]
                curr_act = scenes[end - 1].get("act_number")
                next_act = scenes[next_start].get("act_number")
                gap_seconds = (
                    ACT_PAUSE_SECONDS
                    if curr_act and next_act and curr_act != next_act
                    else CHUNK_PAUSE_SECONDS
                )
                combined.append(torch.zeros((1, int(model.sr * gap_seconds)), dtype=wav.dtype))

        full_wave = torch.cat(combined, dim=-1)
        peak = full_wave.abs().max()
        gain = 0.94 / peak.item() if peak.item() > 0 else 1.0
        if peak.item() > 0:
            full_wave = full_wave * gain
        generated_chunks = [
            (start, end, wav * gain)
            for start, end, wav in generated_chunks
        ]

        # Scene WAVs are cut from grouped narration for review/subtitle timing,
        # not independently synthesized. Renderer uses the uninterrupted master take.
        scene_waves = [None] * len(scenes)
        for start, end, chunk_wave in generated_chunks:
            pieces = _split_waveform_by_text(chunk_wave, texts[start:end])
            for offset, piece in enumerate(pieces):
                scene_waves[start + offset] = piece

        scene_durations = []
        for index, scene_wave in enumerate(scene_waves, 1):
            if scene_wave is None or scene_wave.shape[-1] <= 0:
                raise RuntimeError(f"Could not derive the audio preview for Long-form scene {index}.")
            scene_path = target_dir / f"scene_{index:02d}.wav"
            torchaudio.save(str(scene_path), scene_wave, model.sr)
            scene_durations.append(round(scene_wave.shape[-1] / model.sr, 6))

        master_path = target_dir / "longform_master.wav"
        torchaudio.save(str(master_path), full_wave, model.sr)
        total_duration = full_wave.shape[-1] / model.sr

        manifest = {
            "signature": signature,
            "model_version": selected_model,
            "chunk_ids": chunk_ids,
            "scene_durations": scene_durations,
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
            chunk_ids=chunk_ids,
            model_version=selected_model,
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
