"""Pipeline integration test — no real API calls, no pytest required.

Tests Phase 1 (script analysis) and Phase 2 (prompt generation) end-to-end
using mocked Gemini responses. Validates word counts, dash detection, clip
count, ProductionBrief structure, and ClipPrompt structure.

Run with:
    python -m backend.tests.test_pipeline
"""

import json
import re
import sys
import traceback
import unittest.mock
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Patch external dependencies before any backend imports
# ─────────────────────────────────────────────────────────────────────────────
import types

def _stub_google():
    google_mod = types.ModuleType("google")
    genai_mod  = types.ModuleType("google.genai")
    types_mod  = types.ModuleType("google.genai.types")
    google_mod.genai = genai_mod
    genai_mod.Client = unittest.mock.MagicMock
    genai_mod.types  = types_mod
    for attr in ["GenerateContentConfig", "GenerateImagesConfig",
                 "GenerateVideosConfig", "Image", "Content", "Part", "Blob"]:
        setattr(types_mod, attr, unittest.mock.MagicMock)
    sys.modules["google"]            = google_mod
    sys.modules["google.genai"]      = genai_mod
    sys.modules["google.genai.types"] = types_mod

_stub_google()

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Gemini responses (what a real Phase-1 call would return)
# ─────────────────────────────────────────────────────────────────────────────
MOCK_BRIEF_6: dict = {
    "clips": [
        {"clip_number": 1, "duration_seconds": 8,
         "dialogue": "Teen attempt ho gaye, prelims clear nahi hua, gharwale bol rahe hain chhod de ya shaadi kar le",
         "word_count": 17, "emotional_state": "confided vulnerability",
         "end_emotion": "soft downward gaze, lips parting, quiet resignation settling"},
        {"clip_number": 2, "duration_seconds": 8,
         "dialogue": "Ek raat Rishika didi ki video dekhi, unhone ek sawaal poocha jo andar ghus gaya",
         "word_count": 14, "emotional_state": "cautious discovery",
         "end_emotion": "eyebrow slightly raised, eyes wide, head tilting left with curiosity"},
        {"clip_number": 3, "duration_seconds": 7,
         "dialogue": "Main baith gayi apne aap ke saath, pehli baar roya bhi aur samjhi bhi",
         "word_count": 14, "emotional_state": "vulnerable breakthrough",
         "end_emotion": "eyes glistening, soft exhale, small genuine smile arriving"},
        {"clip_number": 4, "duration_seconds": 7,
         "dialogue": "Rishika didi ne kaha pehle neend theek karo, ek hafte mein fark dikh gaya",
         "word_count": 14, "emotional_state": "quiet confidence",
         "end_emotion": "calm nod, relaxed jaw, warm eyes half-closed in contentment"},
        {"clip_number": 5, "duration_seconds": 8,
         "dialogue": "Abhi bhi uncertain hoon lekin andar se ek zyada sthirta aa gayi hai, yeh meri life hai",
         "word_count": 15, "emotional_state": "grounded resolve",
         "end_emotion": "steady gaze, chin level, small knowing smile, shoulders settled"},
        {"clip_number": 6, "duration_seconds": 5,
         "dialogue": "SuperLiving pe Rishika didi se baat karo, pehla session free hai",
         "word_count": 11, "emotional_state": "warm open invitation",
         "end_emotion": "full warm smile, eyes bright, head slightly forward, open expression"},
    ],
    "character": {
        "age": 29,
        "gender": "female",
        "skin_tone": "medium wheatish",
        "skin_hex": "#C68642",
        "face_shape": "round with soft jaw",
        "hair": "thick black hair, lightly oiled, loose bun with two strands framing face",
        "outfit": "plain cotton salwar in faded blue, white dupatta pinned to left shoulder, visible ironing creases",
        "accessories": ["small red bindi center forehead", "two green glass bangles right wrist"],
        "distinguishing_marks": ["small mole left cheek below eye", "slight kajal smudge right eye"],
    },
    "locked_background": (
        "Small bedroom in a Tier 3 town. Left edge: a painted brick wall with a faded "
        "Ganesha calendar slightly crooked. Right edge: cheap wood-laminate almari with "
        "one door slightly ajar, a plastic water bottle on top. Center-left: white wall "
        "with a grey power socket visible at shoulder height. Foreground soft blur: edge "
        "of a charpoy bedsheet in dull orange cotton. Mid-ground behind subject: a thin "
        "yellow curtain, natural daylight filtering through, creating soft uneven exposure. "
        "Lower-right corner: a steel tumbler on the floor near the charpoy leg. "
        "पृष्ठभूमि पूरी तरह स्थिर और अपरिवर्तित रहती है।"
    ),
    "aspect_ratio": "9:16",
    "coach": "Rishika",
    "setting": "bedroom",
}

MOCK_PROMPTS_6: list = [
    {
        "clip_number": i + 1,
        "duration_seconds": MOCK_BRIEF_6["clips"][i]["duration_seconds"],
        "scene_summary": f"Clip {i+1} emotional beat",
        "prompt": (
            f"FACE LOCK STATEMENT: ⚠️ चेहरा पूरी तरह स्थिर और क्लिप 1 के समान रहेगा।\n\n"
            f"OUTFIT & APPEARANCE: plain cotton salwar in faded blue, white dupatta.\n\n"
            f"LOCATION: Small bedroom Tier 3 town. Left edge: faded Ganesha calendar. "
            f"पृष्ठभूमि पूरी तरह स्थिर और अपरिवर्तित रहती है।\n\n"
            f"ACTION: (STATIC SHOT) Head level, slow exhale. शरीर बिल्कुल स्थिर, हाथ फ्रेम से बाहर।\n\n"
            f"DIALOGUE: चरित्र: \"(बातचीत के लहजे में) {MOCK_BRIEF_6['clips'][i]['dialogue']}\"\n\n"
            f"AUDIO: crystal-clear, studio-quality, close-mic recording।\n\n"
            f"CAMERA: टाइट मीडियम क्लोज-अप (TIGHT MCU)।\n\n"
            f"LIGHTING: PRIMARY warm side-fill। ⚠️ आँखें clearly visible।\n\n"
            f"VISUAL FORMAT PROHIBITIONS: No cinematic letterbox bars. Full 9:16 vertical portrait frame.\n\n"
            f"LAST FRAME: Sitting upright. चेहरा: {MOCK_BRIEF_6['clips'][i]['end_emotion']}।"
        ),
        "dialogue": MOCK_BRIEF_6["clips"][i]["dialogue"],
        "word_count": MOCK_BRIEF_6["clips"][i]["word_count"],
        "end_emotion": MOCK_BRIEF_6["clips"][i]["end_emotion"],
    }
    for i in range(6)
]

MOCK_VERIFIER_REPORT: dict = {
    "clips": [
        {"clip": i + 1, "status": "pass", "issues": []}
        for i in range(6)
    ],
    "overall_score": 100,
    "summary": "All clips passed verification.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
WORD_RANGES = {8: (15, 19), 7: (13, 17), 5: (10, 13)}
DASH_RE = re.compile(r"[—\-]")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")

def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}")
    _failures.append(msg)

def info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")

_failures: list[str] = []

def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")

# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 tests
# ─────────────────────────────────────────────────────────────────────────────
def test_phase1(generate_json_mock):
    section("PHASE 1 — Script Analysis")

    generate_json_mock.return_value = MOCK_BRIEF_6

    from backend.pipeline.phase1_analyser import analyse_script
    from backend.tests.sample_script import SAMPLE_SCRIPT_MRK1, SAMPLE_COACH

    brief = analyse_script(SAMPLE_SCRIPT_MRK1, num_clips=6, coach=SAMPLE_COACH)

    # ── Clip count ────────────────────────────────────────────────────────────
    if len(brief.clips) == 6:
        ok(f"Clip count: {len(brief.clips)}")
    else:
        fail(f"Expected 6 clips, got {len(brief.clips)}")

    # ── Character fields ──────────────────────────────────────────────────────
    c = brief.character
    if c.skin_hex:
        ok(f"skin_hex present: {c.skin_hex}")
    else:
        fail("skin_hex is missing")

    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    if hex_re.match(c.skin_hex):
        ok(f"skin_hex is valid CSS hex: {c.skin_hex}")
    else:
        fail(f"skin_hex invalid format: {c.skin_hex!r}")

    # ── Locked background length ───────────────────────────────────────────────
    bg_words = len(brief.locked_background.split())
    if bg_words >= 50:
        ok(f"locked_background length: {bg_words} words")
    else:
        fail(f"locked_background too short: {bg_words} words (min 50)")

    # ── Per-clip validation ───────────────────────────────────────────────────
    print()
    print(f"  {DIM}Per-clip validation:{RESET}")
    for clip in brief.clips:
        dur = clip.duration_seconds
        lo, hi = WORD_RANGES.get(dur, (0, 9999))
        wc = len(clip.dialogue.split())

        # Word count
        if lo <= wc <= hi:
            ok(f"  Clip {clip.clip_number} word count {wc} in [{lo},{hi}] for {dur}s")
        else:
            fail(f"  Clip {clip.clip_number} word count {wc} outside [{lo},{hi}] for {dur}s")

        # Dashes
        if DASH_RE.search(clip.dialogue):
            fail(f"  Clip {clip.clip_number} contains dashes: {clip.dialogue!r}")
        else:
            ok(f"  Clip {clip.clip_number} dialogue is dash-free")

        # end_emotion
        if clip.end_emotion:
            ok(f"  Clip {clip.clip_number} has end_emotion")
        else:
            fail(f"  Clip {clip.clip_number} missing end_emotion")

    # ── Print brief ───────────────────────────────────────────────────────────
    print(f"\n  {DIM}ProductionBrief JSON:{RESET}")
    brief_dict = brief.model_dump()
    # Truncate locked_background for display
    brief_dict["locked_background"] = brief_dict["locked_background"][:120] + "…"
    print("  " + json.dumps(brief_dict, indent=2, ensure_ascii=False).replace("\n", "\n  "))

    return brief


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 tests
# ─────────────────────────────────────────────────────────────────────────────
def test_phase2(generate_json_mock, brief):
    section("PHASE 2 — Prompt Generation")

    # First call (generate_prompts) → prompts array
    # Second call (verify_prompts)  → verifier report
    generate_json_mock.side_effect = [MOCK_PROMPTS_6, MOCK_VERIFIER_REPORT]

    from backend.pipeline.phase2_prompter import generate_prompts

    clip_prompts = generate_prompts(brief)

    if len(clip_prompts) == 6:
        ok(f"Clip prompt count: {len(clip_prompts)}")
    else:
        fail(f"Expected 6 clip prompts, got {len(clip_prompts)}")

    required_sections = [
        "FACE LOCK STATEMENT",
        "OUTFIT & APPEARANCE",
        "LOCATION",
        "ACTION",
        "DIALOGUE",
        "AUDIO",
        "CAMERA",
        "LIGHTING",
        "VISUAL FORMAT PROHIBITIONS",
        "LAST FRAME",
    ]

    print(f"\n  {DIM}Per-clip prompt validation:{RESET}")
    for cp in clip_prompts:
        issues = []

        # Required sections
        for sec in required_sections:
            if sec not in cp.prompt:
                issues.append(f"missing section: {sec}")

        # Dash-free dialogue
        if DASH_RE.search(cp.dialogue):
            issues.append("dashes in dialogue")

        # Verified flag
        if not cp.verified:
            issues.append("verified=False after verifier pass")

        if issues:
            fail(f"Clip {cp.clip_number}: {'; '.join(issues)}")
        else:
            ok(f"Clip {cp.clip_number}: all {len(required_sections)} sections present, dash-free, verified")

    # ── Print prompts ─────────────────────────────────────────────────────────
    print(f"\n  {DIM}First clip prompt (truncated):{RESET}")
    if clip_prompts:
        truncated = clip_prompts[0].prompt[:600] + "…"
        for line in truncated.splitlines():
            print(f"  {line}")

    return clip_prompts


# ─────────────────────────────────────────────────────────────────────────────
# Standalone validation helpers (no API calls needed)
# ─────────────────────────────────────────────────────────────────────────────
def test_word_count_rules():
    section("WORD COUNT RULE VALIDATION")

    from backend.pipeline.phase1_analyser import _count_words, _trim_dialogue, _expand_dialogue

    cases = [
        # 8s range = 15–19 words
        ("Teen attempt ho gaye prelims clear nahi hua gharwale bol rahe hain chhod de ya shaadi kar le",
         8, True),   # 17 words — in range
        ("Yeh bahut zyada lambi line hai jo definitely exceed karengi ek baar mein limit aur bhi aur bhi kyunki main test kar rahi hoon",
         8, False),  # 24 words — over 19
        ("Chhota",
         8, False),  # 1 word — under 15
        # 7s range = 13–17 words
        ("Rishika didi ki advice se mujhe bahut fark pada, dil mein ek chain aayi",
         7, True),   # 14 words — in range
    ]

    for dialogue, dur, should_pass in cases:
        lo, hi = WORD_RANGES[dur]
        wc = _count_words(dialogue)
        in_range = lo <= wc <= hi
        label = "in-range" if in_range else "out-of-range"
        if in_range == should_pass:
            ok(f"{dur}s clip | {wc} words → {label} (expected {should_pass})")
        else:
            fail(f"{dur}s clip | {wc} words → {label} (expected {should_pass})")

    # Trim test
    long_line = "yeh ek bahut lambi baat hai jo clearly exceed karengi limit aaj raat ko"
    trimmed = _trim_dialogue(long_line, 15)
    wc = _count_words(trimmed)
    if wc <= 15:
        ok(f"_trim_dialogue → {wc} words (target ≤15): {trimmed!r}")
    else:
        fail(f"_trim_dialogue produced {wc} words, expected ≤15")

    # Expand test
    short = "Bahut achha laga"
    expanded, new_wc = _expand_dialogue(short, 13)
    if new_wc >= 13:
        ok(f"_expand_dialogue → {new_wc} words (target ≥13)")
    else:
        fail(f"_expand_dialogue produced only {new_wc} words, expected ≥13")


def test_dash_detection():
    section("DASH DETECTION")

    from backend.pipeline.phase1_analyser import _remove_dashes

    cases = [
        ("Normal dialogue bina dashes ke", False),
        ("Yeh — ek test hai", True),
        ("Self-care zaroori hai", True),
        ("Comma, aur fir aur bhi", False),
    ]

    for text, has_dash in cases:
        found = bool(DASH_RE.search(text))
        if found == has_dash:
            ok(f"{'has' if has_dash else 'no'} dash detected correctly: {text!r}")
        else:
            fail(f"dash detection wrong for: {text!r}")

    # Remove test
    with_dash = "Main — bahut thak gayi hoon, self-care nahi kar pa rahi"
    cleaned   = _remove_dashes(with_dash)
    if not DASH_RE.search(cleaned):
        ok(f"_remove_dashes cleaned: {cleaned!r}")
    else:
        fail(f"_remove_dashes left dashes in: {cleaned!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}Flash Tool v2 — Pipeline Test Suite{RESET}")
    print(f"{DIM}(Phases 1 & 2 only — Veo/Imagen mocked){RESET}\n")

    with unittest.mock.patch(
        "backend.ai.gemini_client.GeminiClient._call",
        return_value='{"dummy": true}',
    ):
        with unittest.mock.patch(
            "backend.ai.gemini_client.GeminiClient.generate_json",
        ) as gj_mock:
            try:
                test_word_count_rules()
                test_dash_detection()
                brief = test_phase1(gj_mock)
                gj_mock.reset_mock()
                test_phase2(gj_mock, brief)
            except Exception:
                traceback.print_exc()
                _failures.append("Unhandled exception — see traceback above")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═'*60}{RESET}")
    if _failures:
        print(f"{BOLD}{RED}FAILED — {len(_failures)} assertion(s){RESET}")
        for f in _failures:
            print(f"  {RED}• {f}{RESET}")
        sys.exit(1)
    else:
        print(f"{BOLD}{GREEN}ALL TESTS PASSED{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
