"""
video/planner.py
~~~~~~~~~~~~~~~~
Intelligent Video Planning Engine:
- Dynamically determines optimal number of scenes based on target duration & pacing.
- Calculates precise scene duration and visual importance (Hero / Core / Supporting / Outro).
- Budgets narration word counts to ensure speech perfectly fits scene timing.
- Calculates transition timing (start/end timestamps, transition types, overlap).
- Calculates subtitle timing (HH:MM:SS,mmm) and FFmpeg synchronization parameters.
"""

import json
import re
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

from text.qwen_service import generate_with_qwen, QwenServiceError
from .schemas import PlannedScene, IntelligentVideoPlan, VideoPlanRequest

logger = logging.getLogger(__name__)

WORDS_PER_SECOND_STANDARD = 2.5   # average speaking rate (~150 wpm)

# Canonical pacing profiles shared with the Video Studio UI labels.
PACING_SCENE_SECONDS = {
    "fast": 3.5,       # high energy, viral, shorts
    "balanced": 5.0,   # standard documentary, default
    "cinematic": 7.0,  # atmospheric, immersive
}

# Tone -> Edge TTS prosody rate so the selected Tone is audible in the
# voiceover, not just present in the storyboard prompt text.
TONE_TTS_RATE = {
    "Professional": "+0%",
    "Cinematic": "-10%",
    "Inspiring": "+5%",
    "Educational": "-5%",
    "Authoritative": "-5%",
    "Casual": "+10%",
}


def normalize_pacing(pacing: str = "balanced") -> str:
    """Coerce any pacing input to fast | balanced | cinematic (default balanced)."""
    cleaned = (pacing or "balanced").lower().strip()
    return cleaned if cleaned in PACING_SCENE_SECONDS else "balanced"


def normalize_tone(tone: str = "Professional") -> str:
    """Coerce tone input to a known studio tone (default Professional)."""
    cleaned = (tone or "Professional").strip().title()
    return cleaned if cleaned in TONE_TTS_RATE else "Professional"


def tts_rate_for_tone(tone: str = "Professional") -> str:
    """Edge TTS rate string (e.g. '+5%') for a studio tone."""
    return TONE_TTS_RATE.get(normalize_tone(tone), "+0%")


def seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert a float seconds value to standard SRT timestamp format HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def determine_scene_count(target_duration: float, pacing: str = "balanced") -> int:
    """
    Determine the optimal number of scenes based on target duration and pacing.

    Standard pacing profiles:
    - 'fast': ~3.5s per scene (high energy, viral, shorts, dynamic tempo)
    - 'balanced': ~5.0s per scene (standard documentary, balanced story, default)
    - 'cinematic': ~7.0s per scene (atmospheric, immersive depth, cinematic narrative)
    """
    pacing_lower = normalize_pacing(pacing)
    avg_scene_len = PACING_SCENE_SECONDS[pacing_lower]

    raw_count = target_duration / avg_scene_len
    scene_count = max(2, min(24, int(round(raw_count))))
    return scene_count


def apply_exact_durations(scenes: list, target_duration: float) -> list:
    """Evenly distribute exact target duration across scenes, resolving rounding differences."""
    count = len(scenes)

    if count == 0:
        return scenes

    base = target_duration / count

    for i, scene in enumerate(scenes):
        scene["duration"] = round(base, 2)

    # Correct rounding difference
    total = sum(scene["duration"] for scene in scenes)
    difference = round(target_duration - total, 2)

    scenes[-1]["duration"] = round(
        scenes[-1]["duration"] + difference,
        2
    )

    return scenes


def calculate_scene_durations(
    target_duration: float,
    num_scenes: int,
    importance_weights: Optional[List[float]] = None
) -> List[float]:
    """
    Distribute the target duration across scenes according to importance weights,
    guaranteeing that the sum strictly equals target_duration.
    """
    if num_scenes <= 0:
        return [target_duration]

    dummy_scenes = [{"duration": 0.0} for _ in range(num_scenes)]
    apply_exact_durations(dummy_scenes, target_duration)

    if not importance_weights or len(importance_weights) != num_scenes:
        return [s["duration"] for s in dummy_scenes]

    total_weight = sum(importance_weights)
    if total_weight <= 0:
        total_weight = 1.0

    durations = [round((w / total_weight) * target_duration, 2) for w in importance_weights]
    durations = [max(2.0, d) for d in durations]
    scale = target_duration / sum(durations)
    durations = [round(d * scale, 2) for d in durations]
    diff = round(target_duration - sum(durations), 2)
    durations[-1] = round(durations[-1] + diff, 2)
    return durations


def estimate_narration_duration(text: str, speech_rate: float = WORDS_PER_SECOND_STANDARD) -> float:
    """Estimate spoken audio duration in seconds from word count."""
    if not text:
        return 0.0
    words = len(text.strip().split())
    return round(words / speech_rate, 2)


def calculate_max_word_budget(duration_seconds: float, speech_rate: float = 2.5) -> int:
    """Calculate the maximum word count for a scene duration to ensure exact video duration without audio rush."""
    return max(3, int(round(duration_seconds * speech_rate)))


VIDEO_SCENE_SYSTEM_PROMPT = """\
You are a STRICT source-grounded AI video storyboard generator.

Your primary responsibility is CONTENT FAITHFULNESS and EXACT TIMING CALIBRATION.

The generated video MUST represent the user's source content.
Do NOT invent unrelated topics, technologies, products, companies,
people, locations, or concepts.

CONFIGURATION:
- TARGET DURATION: {target_duration} seconds across {num_scenes} scenes (exactly {avg_scene_len}s per scene)
- PACING: {pacing} (Narrative tempo: fast/balanced/cinematic)
- TONE: {tone} (Style profile: Professional, Cinematic, Inspiring, Educational, Authoritative, Casual)
- TARGET AUDIENCE: {audience}
- LANGUAGE: {language}
- MAX WORDS PER SCENE: {max_words_per_scene} words (STRICT LIMIT to prevent speech overrun)

TONE & STYLE GUIDELINES:
- Professional: Clear, objective, polished executive narrative with high-detail focal subject, modern technology displays, and cinematic studio lighting (never empty rooms or vacant tables).
- Cinematic: Dramatic, evocative storytelling with 35mm film aesthetic, dramatic lighting, and deep atmospheric framing.
- Inspiring: Visionary, forward-looking narration with warm, aspirational, golden hour imagery.
- Educational: Explanatory, concept-focused narration with clear illustrative visual prompts.
- Authoritative: Decisive, command-level executive briefing with high-end architectural/industrial framing.
- Casual: Friendly, conversational, approachable narration with vibrant, relatable scenes.

CORE RULES:
1. Read and understand the complete source content first.
2. Extract the core factual concepts and topical themes from the source.
3. Create EXACTLY {num_scenes} scenes representing those concepts.
4. Every scene narration MUST NOT exceed {max_words_per_scene} words to preserve the exact {target_duration}s video length.
5. VISUAL PROMPT REQUIREMENTS FOR DIFFUSION:
   - Each 'visual_prompt' MUST describe a concrete, physical, photorealistic scene (subject, physical environment, camera framing, lighting, high detail) matching {tone} style.
   - NEVER describe empty conference rooms, vacant boardroom tables, plain office chairs, or blank sheets of paper.
   - If the source content contains procedural instructions or prompt meta-language (e.g. "Analyze the document", "Extract key facts", "Transform the information", "Ensure accuracy", "Create a LinkedIn post", "Organize clearly"), do NOT depict procedural text or words on paper. Instead, visually depict the actual semantic real-world scenario (e.g., AI neural networks processing complex data streams in high-tech lab, specialists reviewing verified intelligence reports on glowing digital displays).
   - Never output procedural words like "analyze", "extract", "summarize", "instructions", "prompt", "watermark", or "text" inside visual_prompt.
6. The on_screen_text MUST be a punchy 2-4 word banner.
7. Preserve the meaning of the original source without inventing extraneous elements.

SOURCE CONTENT:
{source_text}

Return ONLY valid JSON matching this schema:
{{
  "title": "Video Title",
  "scenes": [
    {{
      "scene_number": 1,
      "source_fact": "Exact factual concept from source text",
      "narration": "Voiceover narration strictly under {max_words_per_scene} words in {tone} tone",
      "visual_prompt": "Photorealistic {tone} visual description of physical scene, subject, lighting, 8k, sharp focus",
      "on_screen_text": "Short headline (max 4 words)",
      "transition_type": "crossfade"
    }}
  ]
}}
"""

PLANNING_PROMPT_TEMPLATE = VIDEO_SCENE_SYSTEM_PROMPT


class IntelligentVideoPlanner:
    """
    Intelligent Video Planning Engine:
    Determines scene counts, durations, visual importance, narration limits,
    transition timing, and subtitle synchronization.
    """

    @classmethod
    def _budget_source(cls, content: str, max_tokens: int = 3000) -> str:
        """Token-aware source clamp (replaces unbounded prompt injection)."""
        try:
            import sys as _sys
            from pathlib import Path as _P

            _b = _P(__file__).resolve().parent.parent
            if str(_b) not in _sys.path:
                _sys.path.insert(0, str(_b))
            from app.core.token_budgets import truncate_to_token_budget

            out, info = truncate_to_token_budget(
                (content or "").strip(), max_tokens, model="qwen", stage="video_plan"
            )
            if info.get("truncated"):
                logger.warning(
                    "video_plan source truncated original=%s kept=%s budget=%s",
                    info.get("original_tokens"),
                    info.get("kept_tokens"),
                    max_tokens,
                )
            return out
        except Exception:
            return (content or "").strip()[:12000]

    @classmethod
    def plan_video(
        cls,
        content: str,
        target_duration: int = 30,
        pacing: str = "balanced",
        language: str = "English",
        tone: str = "Professional",
        audience: str = "General public",
        source_facts: Optional[List[Dict[str, Any]]] = None
    ) -> IntelligentVideoPlan:
        """
        Produce a complete, synchronized Intelligent Video Plan from source content.
        """
        target_dur = float(max(10, min(180, target_duration)))
        pacing = normalize_pacing(pacing)
        tone = normalize_tone(tone)
        num_scenes = determine_scene_count(target_dur, pacing)
        
        # Duration wins over pacing: calculate exact scene duration from target duration
        avg_scene_len = round(target_dur / num_scenes, 2)
        max_words = calculate_max_word_budget(avg_scene_len)

        prompt = VIDEO_SCENE_SYSTEM_PROMPT.format(
            target_duration=int(target_dur),
            num_scenes=num_scenes,
            avg_scene_len=avg_scene_len,
            pacing=pacing,
            tone=tone,
            audience=audience,
            language=language,
            max_words_per_scene=max_words,
            source_text=cls._budget_source(content),
        )

        planned_scenes_raw = []
        video_title = "AI Video Production"

        # Try LLM-driven planning (centralized per-deliverable output budget).
        try:
            try:
                import sys as _sys
                from pathlib import Path as _P

                _b = _P(__file__).resolve().parent.parent
                if str(_b) not in _sys.path:
                    _sys.path.insert(0, str(_b))
                from app.core.token_budgets import resolve_output_budget as _rob

                _np = int(_rob("video_plan", None))
            except Exception:
                _np = 1200
            raw_response = generate_with_qwen(prompt, num_predict=_np, timeout=45)
            data = cls._extract_json(raw_response)
            if isinstance(data, dict):
                video_title = data.get("title", video_title)
                scenes = data.get("scenes", [])
                if isinstance(scenes, list) and len(scenes) >= 2:
                    planned_scenes_raw = scenes[:num_scenes]
        except Exception as e:
            logger.warning(f"IntelligentVideoPlanner LLM call failed: {e}. Using intelligent deterministic planning.")

        # If LLM didn't return adequate scenes, construct rich domain-aware deterministic plan
        if len(planned_scenes_raw) < 2:
            planned_scenes_raw = cls._build_deterministic_scenes(
                content=content,
                num_scenes=num_scenes,
                target_duration=target_dur,
                tone=tone,
                pacing=pacing,
                source_facts=source_facts
            )

        # Build fully calibrated PlannedScene models with exact durations
        planned_scenes = cls._calibrate_scenes(
            scenes_raw=planned_scenes_raw,
            num_scenes=num_scenes,
            target_duration=target_dur
        )

        # Build timeline and FFmpeg sync metadata
        timeline = cls._build_timeline(planned_scenes)
        ffmpeg_sync = cls._build_ffmpeg_sync_metadata(planned_scenes, target_dur)

        total_calc_duration = round(sum(s.duration for s in planned_scenes), 2)

        return IntelligentVideoPlan(
            title=video_title,
            target_duration=target_dur,
            total_calculated_duration=total_calc_duration,
            num_scenes=len(planned_scenes),
            average_scene_duration=round(total_calc_duration / len(planned_scenes), 2),
            pacing=pacing,
            scenes=planned_scenes,
            timeline=timeline,
            ffmpeg_sync_metadata=ffmpeg_sync
        )

    @classmethod
    def _calibrate_scenes(
        cls,
        scenes_raw: List[Dict[str, Any]],
        num_scenes: int,
        target_duration: float
    ) -> List[PlannedScene]:
        """Calibrate timings, visual importance, transitions, and subtitle timestamps."""
        # Normalize count
        if len(scenes_raw) < num_scenes:
            while len(scenes_raw) < num_scenes:
                idx = len(scenes_raw) + 1
                scenes_raw.append({
                    "scene_number": idx,
                    "duration": 5.0,
                    "visual_importance": 0.8,
                    "visual_tier": "MEDIUM",
                    "narration": f"Continuing verified insights in scene {idx}.",
                    "visual_prompt": f"cinematic high-tech visual representing technological progress, photorealistic, 8k",
                    "on_screen_text": "Key Insight",
                    "transition_type": "crossfade"
                })
        elif len(scenes_raw) > num_scenes:
            scenes_raw = scenes_raw[:num_scenes]

        # Extract or compute importance weights
        weights = []
        for s in scenes_raw:
            w = float(s.get("visual_importance", 0.8))
            weights.append(max(0.5, min(1.0, w)))

        # Enforce exact durations distributed across scenes summing to target_duration
        apply_exact_durations(scenes_raw, target_duration)
        durations = [float(s["duration"]) for s in scenes_raw]

        calibrated_scenes: List[PlannedScene] = []
        current_time = 0.0

        for i, (sc, dur) in enumerate(zip(scenes_raw, durations), start=1):
            start_t = round(current_time, 2)
            end_t = round(current_time + dur, 2)
            current_time = end_t

            narration = str(sc.get("narration", f"Scene {i} narration.")).strip()
            max_words = calculate_max_word_budget(dur)
            
            # Ensure narration strictly respects word budget to avoid stretching duration
            words = narration.split()
            if len(words) > max_words:
                narration = " ".join(words[:max_words]).rstrip(" ,;:—-\t\n")
                if not narration.endswith((".", "!", "?")):
                    narration += "."
            
            est_dur = estimate_narration_duration(narration)

            importance = round(weights[i - 1], 2)
            tier = "HIGH" if importance >= 0.85 else ("MEDIUM" if importance >= 0.7 else "LOW")

            trans_type = sc.get("transition_type", "crossfade" if i < num_scenes else "fade")
            trans_dur = 0.5 if i < num_scenes else 0.0

            sub_start = seconds_to_srt_timestamp(start_t)
            sub_end = seconds_to_srt_timestamp(end_t)

            calibrated_scenes.append(PlannedScene(
                scene_number=i,
                duration=dur,
                visual_importance=importance,
                visual_tier=tier,
                narration=narration,
                estimated_narration_duration=est_dur,
                max_word_count=max_words,
                visual_prompt=sc.get("visual_prompt", "cinematic photorealistic shot, 8k"),
                on_screen_text=sc.get("on_screen_text", f"Scene {i}"),
                start_time=start_t,
                end_time=end_t,
                transition_type=trans_type,
                transition_duration=trans_dur,
                subtitle_start=sub_start,
                subtitle_end=sub_end,
                source_facts=sc.get("source_facts", [])
            ))

        return calibrated_scenes

    @classmethod
    def _clean_visual_subject(cls, text: str) -> str:
        """Extract concrete visual subject from raw text, stripping procedural instructions."""
        cleaned = text.strip()
        patterns = [
            r"^(?:analyze|evaluate|review|examine|inspect|read)\s+(?:the|this|following)?\s*(?:document|content|text|data|report)?\s*,?\s*",
            r"^(?:extract|identify|determine|find)\s+(?:its|the|key)?\s*(?:facts|objectives|findings|metrics|insights)?\s*,?\s*",
            r"^(?:summarize|summarise)\s+(?:the|important)?\s*(?:findings|points|information)?\s*,?\s*",
            r"^(?:transform|convert)\s+(?:the)?\s*(?:information|content)?\s*(?:into|to)?\s*(?:multiple\s+formats)?\s*,?\s*",
            r"^(?:ensure|make sure)\s+(?:that)?\s*(?:all|the)?\s*(?:generated\s+outputs|outputs)?\s*,?\s*",
            r"^(?:organize|structure)\s+(?:the|information|content)?\s*,?\s*",
            r"^(?:avoid|prevent)\s+(?:unsupported\s+claims|errors)?\s*,?\s*",
            r"^(?:highlight|focus on)\s+(?:the)?\s*(?:most important)?\s*(?:insights|points)?\s*,?\s*",
            r"^(?:multiple\s+formats|including\s+an?\s+executive\s+summary|a\s+linkedin\s+post).*$",
            r"^(?:including\s+an?\s+|such\s+as\s+|like\s+|in\s+multiple\s+formats\s*)",
        ]
        for pat in patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

        lower = text.lower()
        if "intelligence" in lower or "ai" in lower:
            return "artificial intelligence neural networks processing and visualizing complex data streams in high-tech research lab"
        if "format" in lower or "summary" in lower or "report" in lower:
            return "data analysts reviewing real-time analytics and strategic metrics on luminous holographic screens"
        if "objective" in lower or "insight" in lower or "finding" in lower:
            return "strategic corporate insights visualized on digital matrix displays in modern innovation center"
        if "accuracy" in lower or "accurate" in lower:
            return "data verification system with accurate real-time metrics displayed on futuristic monitors"

        if len(cleaned) < 10:
            return "modern high-tech innovation environment with glowing digital data displays"

        return cleaned.rstrip(" .,;:-")

    @classmethod
    def _build_deterministic_scenes(
        cls,
        content: str,
        num_scenes: int,
        target_duration: float,
        tone: str = "Professional",
        pacing: str = "balanced",
        source_facts: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Construct strictly source-grounded deterministic scenes directly from source content with calibrated tone and pacing."""
        scenes = []
        clean_content = content.strip() if content else "Grounded visual storytelling overview."
        
        avg_dur = target_duration / num_scenes
        word_budget = calculate_max_word_budget(avg_dur)

        tone_style_map = {
            "Cinematic": "cinematic dramatic lighting, 35mm film aesthetic, anamorphic lens, 8k",
            "Inspiring": "warm golden hour lighting, visionary perspective, uplifting atmosphere, 8k",
            "Educational": "clean crisp studio lighting, informative infographic elements, sharp focus, 8k",
            "Authoritative": "high-end architectural framing, powerful composition, modern industrial elegance, 8k",
            "Casual": "vibrant natural daylight, candid authentic framing, relatable modern photography, 8k",
            "Professional": "photorealistic, dynamic professional studio lighting, detailed visual subject, sharp focus, 8k masterpiece"
        }
        visual_suffix = tone_style_map.get(tone, tone_style_map["Professional"])

        # 1. If structured facts are provided, use them directly
        if source_facts and len(source_facts) > 0:
            facts_to_use = source_facts[:num_scenes]
            for idx, fact in enumerate(facts_to_use, 1):
                stmt = fact.get("statement", f"Core metric and fact {idx}.")
                imp = float(fact.get("importance", 0.8))
                words = stmt.split()
                narr = " ".join(words[:word_budget]) if len(words) > word_budget else stmt
                narr = narr.rstrip(" ,;:—-\t\n")
                if not narr.endswith((".", "!", "?")):
                    narr += "."

                scenes.append({
                    "scene_number": idx,
                    "source_fact": stmt,
                    "visual_importance": imp,
                    "visual_tier": "HIGH" if imp >= 0.85 else "MEDIUM",
                    "narration": narr,
                    "visual_prompt": f"detailed shot representing {stmt[:60].lower().rstrip('.')}, {visual_suffix}",
                    "on_screen_text": fact.get("category", f"Key Point {idx}"),
                    "transition_type": "crossfade" if idx < num_scenes else "fade",
                    "source_facts": [fact.get("id", f"F00{idx}")]
                })

            apply_exact_durations(scenes, target_duration)
            return scenes

        # 2. Extract source facts / clauses from user text
        clause_splits = re.split(
            r"(?:[\.\!\?\n]+|;\s*|\s*—\s*|,\s*(?:and|by|with|integrating|featuring|enabling|including|powered by|while)\s*|,\s*|\s+(?:by integrating|by using|powered by|integrating|featuring|enabling|including|as well as)\s+)",
            clean_content,
            flags=re.IGNORECASE
        )
        meaningful_clauses = [c.strip() for c in clause_splits if len(c.strip()) > 4]
        if not meaningful_clauses:
            meaningful_clauses = [clean_content]

        for idx in range(1, num_scenes + 1):
            if idx <= len(meaningful_clauses):
                fact_clause = meaningful_clauses[idx - 1]
            else:
                fact_clause = meaningful_clauses[(idx - 1) % len(meaningful_clauses)]

            # Clean and format
            fact_clause = fact_clause[0].upper() + fact_clause[1:] if len(fact_clause) > 1 else fact_clause
            
            # Formulate concise narration strictly under word budget
            words = fact_clause.split()
            if len(words) > word_budget:
                narr_text = " ".join(words[:word_budget]).rstrip(" ,;:—-\t\n")
            else:
                narr_text = fact_clause.rstrip(" ,;:—-\t\n")
            if not narr_text.endswith((".", "!", "?")):
                narr_text += "."

            # Create punchy headline from clause
            headline = " ".join(words[:min(3, len(words))]).title()

            # Formulate strictly grounded visual prompt representing concrete visual subject
            visual_subject = cls._clean_visual_subject(fact_clause)
            if idx == 1:
                v_prompt = f"establishing cinematic shot of {visual_subject}, {visual_suffix}"
            elif idx == num_scenes:
                v_prompt = f"closing focal shot of {visual_subject}, {visual_suffix}"
            else:
                v_prompt = f"detailed perspective of {visual_subject}, {visual_suffix}"

            imp = 0.9 if (idx == 1 or idx == 2) else 0.75
            scenes.append({
                "scene_number": idx,
                "source_fact": fact_clause,
                "visual_importance": imp,
                "visual_tier": "HIGH" if imp >= 0.85 else "MEDIUM",
                "narration": narr_text,
                "visual_prompt": v_prompt,
                "on_screen_text": headline,
                "transition_type": "crossfade" if idx < num_scenes else "fade",
                "source_facts": []
            })

        apply_exact_durations(scenes, target_duration)
        return scenes

    @classmethod
    def _build_timeline(cls, scenes: List[PlannedScene]) -> List[Dict[str, Any]]:
        """Construct chronological timeline events for playback and UI rendering."""
        timeline = []
        for s in scenes:
            timeline.append({
                "timestamp_start": s.start_time,
                "timestamp_end": s.end_time,
                "scene_number": s.scene_number,
                "type": "scene_display",
                "title": s.on_screen_text,
                "duration": s.duration,
                "narration": s.narration,
                "visual_tier": s.visual_tier,
                "transition": {
                    "type": s.transition_type,
                    "duration": s.transition_duration,
                    "at_seconds": s.end_time
                },
                "subtitle": {
                    "start": s.subtitle_start,
                    "end": s.subtitle_end,
                    "text": s.narration
                }
            })
        return timeline

    @classmethod
    def _build_ffmpeg_sync_metadata(
        cls,
        scenes: List[PlannedScene],
        target_duration: float
    ) -> Dict[str, Any]:
        """Generate exact FFmpeg synchronization parameters."""
        video_filters = []
        concat_durations = []

        for i, s in enumerate(scenes):
            concat_durations.append({
                "scene_number": s.scene_number,
                "exact_seconds": s.duration,
                "tail_padding_seconds": 0.5,
                "audio_sync_offset": s.start_time
            })
            if s.transition_type == "crossfade" and i < len(scenes) - 1:
                video_filters.append(
                    f"xfade=transition=fade:duration={s.transition_duration}:offset={round(s.end_time - s.transition_duration, 2)}"
                )

        return {
            "target_duration_seconds": target_duration,
            "scene_count": len(scenes),
            "video_codec": "libx264",
            "audio_codec": "aac",
            "pixel_format": "yuv420p",
            "crossfade_filters": video_filters,
            "scene_sync_durations": concat_durations,
            "srt_subtitles_count": len(scenes)
        }

    @classmethod
    def _extract_json(cls, raw: str) -> Dict[str, Any]:
        """Extract clean JSON object from LLM response string with robust repair."""
        raw_clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        if "<think>" in raw_clean and "</think>" not in raw_clean:
            brace_positions = [pos for pos in (raw_clean.find("{"), raw_clean.find("[")) if pos != -1]
            if brace_positions:
                raw_clean = raw_clean[min(brace_positions):].strip()

        raw_clean = re.sub(r"^```(?:json)?\s*", "", raw_clean, flags=re.IGNORECASE).strip()
        raw_clean = re.sub(r"\s*```$", "", raw_clean, flags=re.IGNORECASE).strip()

        # 1. Direct parse attempt
        try:
            res = json.loads(raw_clean)
            if isinstance(res, dict):
                return res
            if isinstance(res, list):
                return {"scenes": res}
        except Exception:
            pass

        # 2. Substring extraction
        start = raw_clean.find("{")
        end = raw_clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = raw_clean[start:end + 1]
            try:
                res = json.loads(snippet)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

            # Auto-repair trailing commas
            repaired = re.sub(r",\s*([\]}])", r"\1", snippet)
            try:
                res = json.loads(repaired)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

        # 3. Array substring extraction
        start_arr = raw_clean.find("[")
        end_arr = raw_clean.rfind("]")
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            snippet = raw_clean[start_arr:end_arr + 1]
            repaired = re.sub(r",\s*([\]}])", r"\1", snippet)
            try:
                res = json.loads(repaired)
                if isinstance(res, list):
                    return {"scenes": res}
            except Exception:
                pass

        raise ValueError("Could not extract valid JSON from planner output.")
