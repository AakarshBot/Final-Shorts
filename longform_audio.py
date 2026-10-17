"""Long-form Documentary Audio Synthesis Engine.

Powered by Chatterbox Turbo TTS voice cloning with per-scene temperature modulation,
seed re-randomization, atmospheric act pauses, and linear word timing synthesis
for ~8-minute long-form documentary productions.
"""

from __future__ import annotations

from hashlib import sha1
import io
import os
from pathlib import Path
import re
from typing import Any

from audio import synthesize_linear_timings


_CHATTERBOX_MODEL = None
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_REFERENCE = Path(os.getenv("AUDIO_REFERENCE", ROOT_DIR / "audio_reference.wav"))
LONGFORM_OUTPUT_DIR = ROOT_DIR / "output" / "audio_longform"


def _clean(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def get_chatterbox_model():
    """Lazily loads and caches the Chatterbox Turbo TTS model."""
    global _CHATTERBOX_MODEL
    if _CHATTERBOX_MODEL is None:
        try:
            import torch
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _CHATTERBOX_MODEL = ChatterboxTurboTTS.from_pretrained(device=device)
        except Exception as exc:
            raise RuntimeError(f"Chatterbox Turbo TTS could not be loaded: {exc}") from exc
    return _CHATTERBOX_MODEL


class LongformAudioEngine:
    """Synthesizes high-fidelity voice narration for ~8-minute documentaries."""

    @classmethod
    def generate(
        cls,
        script_data: dict[str, Any],
        run_number: int = 1,
        reference_audio: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        language = str(script_data.get("language_used") or script_data.get("language") or "english").strip().casefold()
        if language not in {"english", "en"}:
            raise ValueError("Long-form Chatterbox Turbo currently supports English narration only.")

        scenes = list(script_data.get("scenes") or [])
        if not scenes:
            raise ValueError("The approved Long-form script contains no scenes.")

        for number, sc in enumerate(scenes, 1):
            text = _clean(sc.get("voiceover"))
            if not text:
                raise ValueError(f"Scene {number} has no voiceover narration.")

        import torch
        import torchaudio

        model = get_chatterbox_model()

        # Output folder setup
        key = sha1(" ".join(sc["voiceover"] for sc in scenes).encode("utf-8")).hexdigest()[:12]
        target_dir = Path(output_dir or (LONGFORM_OUTPUT_DIR / key))
        target_dir.mkdir(parents=True, exist_ok=True)
        for old in target_dir.glob("*.wav"):
            try:
                old.unlink()
            except OSError:
                pass

        # Reference voice preparation
        ref_path = Path(reference_audio) if reference_audio else DEFAULT_REFERENCE
        actual_ref = ref_path if ref_path.is_file() else None
        if actual_ref:
            try:
                model.prepare_conditionals(str(actual_ref), exaggeration=0.5)
            except Exception as exc:
                raise RuntimeError(
                    f"Chatterbox could not use the voice reference file '{actual_ref}': {exc}. "
                    "Replace the file or remove it to use Chatterbox's built-in voice."
                ) from exc

        waves = []
        scene_paths = []
        scene_durations = []
        scene_timings = []
        cumulative_time = 0.0

        for number, sc in enumerate(scenes, 1):
            text = _clean(sc.get("voiceover"))
            if not text:
                raise ValueError(f"Scene {number} has no voiceover narration.")

            # Seed re-randomization per run & scene
            seed = run_number * 1000 + number
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

            # Documentary temperature modulation
            act_num = sc.get("act_number", 1)
            temperature = 0.80
            if act_num == 1:
                temperature = 0.88  # Higher urgency on hook
            elif act_num == 5:
                temperature = 0.85  # Climax intensity
            elif act_num == 6 and number == len(scenes):
                temperature = 0.82  # Reflective closing

            wav = model.generate(text, temperature=temperature)
            wav = wav.detach().cpu()
            if wav.ndim == 1:
                wav = wav.unsqueeze(0)

            dur = wav.shape[-1] / model.sr
            waves.append(wav)
            scene_durations.append(dur)

            # Save individual scene wave
            sc_path = target_dir / f"scene_{number:02d}.wav"
            torchaudio.save(str(sc_path), wav, model.sr)
            scene_paths.append(str(sc_path))

            # Synthesize linear word timestamps for subtitles
            timings = synthesize_linear_timings(text, dur)
            scene_timings.append({
                "scene": number,
                "act": act_num,
                "path": str(sc_path),
                "duration": round(dur, 3),
                "start_seconds": round(cumulative_time, 3),
                "timings": timings,
            })
            cumulative_time += dur + 0.15  # Small breath gap between scenes

        # Atmospheric pause between acts (0.8s) and small gap between scenes (0.15s)
        act_pause_samples = int(model.sr * 0.80)
        scene_pause_samples = int(model.sr * 0.15)
        act_silence = torch.zeros((1, act_pause_samples))
        scene_silence = torch.zeros((1, scene_pause_samples))

        combined = []
        for idx, (wav, sc) in enumerate(zip(waves, scenes)):
            combined.append(wav)
            if idx < len(waves) - 1:
                next_act = scenes[idx + 1].get("act_number")
                curr_act = sc.get("act_number")
                if next_act and curr_act and next_act != curr_act:
                    combined.append(act_silence)  # Inter-act pause
                else:
                    combined.append(scene_silence)

        full_wave = torch.cat(combined, dim=-1)
        peak = full_wave.abs().max()
        if peak.item() > 0:
            full_wave = full_wave * (0.94 / peak)  # Normalize peak to 0.94

        master_path = target_dir / "longform_master.wav"
        torchaudio.save(str(master_path), full_wave, model.sr)
        total_duration = full_wave.shape[-1] / model.sr

        return {
            "master_path": str(master_path),
            "scene_paths": scene_paths,
            "scene_durations": scene_durations,
            "scenes": scene_timings,
            "total_duration": round(total_duration, 2),
            "engine": "Chatterbox-Turbo",
            "reference": str(actual_ref) if actual_ref else "Built-in Chatterbox neural voice",
            "run_number": run_number,
        }

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

