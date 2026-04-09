SYSTEM_IMAGER = """
You are the Keyframe Transition Architect for SuperLiving's video ad pipeline.

You receive:
  1. The previous clip's LAST FRAME image (as a base64 image input)
  2. The target end_emotion for that frame (a specific expression description)
  3. The character spec (outfit, appearance, skin tone, accessories)
  4. The locked background description

Your job: generate a new image that is IDENTICAL to the input image in every way
EXCEPT the character's facial expression, which must transition to the target end_emotion.

This output image will be used as the reference/first-frame image for Veo video generation
of the next clip. It must be photorealistic, consistent, and pass Veo's image conditioning.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO CHANGE — ONLY THE EXPRESSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHANGE: The character's facial expression to match end_emotion exactly.
  • Target the specific muscle groups described in end_emotion
  • If end_emotion says "soft smile, left lip corner raised 2mm" — render that precisely
  • If end_emotion says "eyes 80% open, slight upward gaze" — render that precisely
  • Expression change should feel like a photograph taken 1 second after the last frame
  • Mouth should be closed or just closing (character has just finished speaking)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT MUST REMAIN IDENTICAL — NEVER CHANGE THESE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IDENTITY — SAME PERSON, NOT SIMILAR-LOOKING PERSON:
This is the same individual as the input image. Not a lookalike. Not a similar type.
The EXACT same person. If it looks like a different person — regenerate.

FACE STRUCTURE: bone structure, nose shape, lip thickness, ear shape, eye shape,
eyebrow shape and thickness, face width, jawline, chin shape.
Any deviation in face structure will break character consistency across the ad.

SKIN: tone (#HEX from spec), texture (visible pores, natural imperfections — DO NOT
smooth or beautify skin, preserve every pore and mark), any moles or marks at their
exact locations, any kajal smudge — all unchanged.

HAIR: same style, same parting, same looseness, same sheen.
DO NOT change the hair — every strand must be in the same position.
Same stray strands framing the face in the same positions.

OUTFIT: identical garment, identical color, identical pattern, identical fit.
Same drape of dupatta. Same safety pin position. Same ironing creases.

ACCESSORIES: every item at identical position — bindi (size, color, position),
bangles (which wrist, how many, what color), mangalsutra (length, where it falls),
earrings (style, which ear visible), nose ring if present.

CAMERA FRAME: TIGHT MCU — chin to mid-chest, eye-level. Same crop. Same framing.
The subject occupies the same proportion of the frame.

BACKGROUND: every single object in exact same position with identical color.
No new objects. No removed objects. No lighting shift in the background.
DO NOT change the background — identical object positions and colors.

LIGHTING: same direction (45° warm side-fill, consistent side across clips),
same color temperature, same secondary ambient fill from overhead.
Eye sockets clearly lit — no dark shadows.

HEAD POSITION: same tilt, same turn, same height in frame. Only expression changes.

EYE NATURALNESS: soft focus on camera lens, natural blink position (eyes 70-80% open
for neutral/resting states), not wide-open robotic stare, not glazed unfocused.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNICAL REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output format  : 9:16 vertical portrait (1080 × 1920)
Style          : photorealistic, not illustrated, not painterly, not stylized
Skin rendering : visible pores, natural micro-texture, no airbrushing, no smoothing
No text        : no subtitles, no watermarks, no UI overlays
No letterbox   : frame must be full edge-to-edge, no black bars
Lighting       : cinematic contrast but not dramatic — warm and natural
Quality        : ultra-sharp focus, 8k equivalent detail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTI-DRIFT QUALITY CHECKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before finalizing output, verify:
□ Is this the SAME PERSON as the input? (not similar-looking — same person)
□ Is skin texture unchanged? (pores, marks, kajal in same positions)
□ Is hair unchanged? (every strand, every stray hair, same parting)
□ Is outfit unchanged? (every crease, drape, safety pin position)
□ Are all accessories present? (bindi, bangles, mangalsutra — exact positions)
□ Is background unchanged? (every object, every position, no new objects)
□ Is head position unchanged? (only expression changed)
□ Are eye sockets lit? (no dark shadows)
□ Are eyes natural? (not robotic wide-open, not glazed)

If it looks like a different person — regenerate.
If skin has been airbrushed or smoothed — regenerate.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# IMAGEN 4 — INITIAL CHARACTER REFERENCE IMAGE
# ─────────────────────────────────────────────────────────────────────────────

def build_imagen_prompt(
    physical_baseline: str,
    outfit: str,
    gender: str,
    opening_emotion: str,
    locked_background: str,
) -> str:
    """Build the Imagen 4 text-to-image prompt for the initial character reference frame (keyframe 0).

    Args:
        physical_baseline: Full physical description (age, skin tone, hex, face shape, hair, marks).
        outfit:            Full outfit description (every garment, color, fabric, ironing creases).
        gender:            Character gender (e.g., "female", "महिला").
        opening_emotion:   The emotional_state of clip 1 (e.g., "confided vulnerability at raat 11").
        locked_background: The full 60+ word locked background description.

    Returns:
        Fully formatted Imagen prompt string.
    """
    gender_word = "woman" if "female" in gender.lower() or "महिला" in gender else "person"
    return (
        f"Hyper-realistic smartphone photo of an everyday Indian {gender_word}. "
        f"{physical_baseline}. Wearing {outfit}. "
        f"Shot on an ordinary mid-range Android smartphone: slight overexposure on one side, "
        f"no ring light, no softbox, no studio lighting setup, natural slightly uneven exposure. "
        f"Skin tone: warm brown to medium brown — NOT fair, NOT light-skinned, NOT model-complexion. "
        f"Build: average, ordinary — NOT gym-fit, NOT model-thin, NOT aspirational. "
        f"Ultra-realistic skin texture with visible pores, no airbrushing, no beauty mode, no skin smoothing filter. "
        f"Expression: direct, slightly self-conscious eye contact with the camera lens — like "
        f"someone about to say something personal to a close friend, not performing for an audience. "
        f"Slight tension in the jaw or eyes suggesting they are about to share something real. "
        f"NOT smiling for a photo. NOT posing. Just present and honest. "
        f"Opening emotional state: {opening_emotion}. "
        f"Clothing looks lived-in, not brand new. Hair naturally styled at home, not salon-done. "
        f"Looks authentically like their stated occupation and life stage — "
        f"a housewife looks like she has been home all day, "
        f"an office worker looks like they just finished a long shift, "
        f"a student looks like they haven't slept enough. "
        f"Completely unretouched. Looks like a real person recording a UGC video at home. "
        f"Setting: {locked_background} "
        f"Tight medium close-up shot, chin to mid-chest, eye-level, camera absolutely still. "
        f"Subject fills 70–80% of the frame vertically. "
        f"Format: 9:16 vertical portrait (1080×1920). Full frame edge to edge — no black bars, "
        f"no letterbox, no UI overlays, no subtitles, no watermarks. "
        f"Photorealistic, not illustrated. Skin has natural variation and imperfection. "
        f"Lighting: warm soft side-fill from the left (45°), secondary overhead ambient "
        f"fill to eliminate eye-socket shadows. Eyes clearly visible and sharp. "
        f"Cinematic contrast but warm and approachable — not harsh, not dramatic. "
        f"Ultra-sharp focus, 8k detail equivalent."
    )


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI FLASH IMAGE — TRANSITION FRAME USER MESSAGE
# ─────────────────────────────────────────────────────────────────────────────

def build_transition_frame_prompt(
    end_emotion: str,
    clip_number: int,
    total_clips: int,
) -> str:
    """Build the user message for the Gemini Flash Image expression edit call.

    This generates keyframe[clip_number] — the ENDING frame of clip[clip_number-1],
    which is also the STARTING frame of clip[clip_number].

    Args:
        end_emotion:   The target end expression from ClipPrompt.end_emotion.
        clip_number:   1-based clip number whose end-frame this produces.
        total_clips:   Total number of clips in the ad.

    Returns:
        User message string to send with the previous keyframe image.
    """
    prev_keyframe = clip_number - 1
    return (
        f"Look at the provided image. This is keyframe {prev_keyframe} — "
        f"the starting frame of Clip {clip_number}.\n\n"
        f"Generate keyframe {clip_number} — the ENDING frame of Clip {clip_number} "
        f"(out of {total_clips} total clips).\n\n"
        f"TARGET EXPRESSION: {end_emotion}\n\n"
        f"SETTLE-TO-REST CONTEXT: The character has just finished speaking. "
        f"They are settling to a rest position. "
        f"Mouth should be closed or just closing — the speaking is done.\n\n"
        f"KEEP EVERYTHING ELSE PIXEL-PERFECT IDENTICAL:\n"
        f"  — Face structure, bone structure, skin texture, all moles and marks\n"
        f"  — Skin tone (preserve pores and natural texture — DO NOT smooth or beautify)\n"
        f"  — Hair: DO NOT change the hair — every strand in same position\n"
        f"  — Outfit: identical garment, identical color, identical drape\n"
        f"  — Accessories: every item at identical position\n"
        f"  — Background: every object in every exact position — DO NOT change background\n"
        f"  — Camera framing: TIGHT MCU, chin to mid-chest, eye-level\n"
        f"  — Lighting: same direction, same temperature, same shadow fill\n"
        f"  — Head position: same tilt and turn — ONLY the expression changes\n"
        f"  — Eye naturalness: soft focus on camera, natural blink position, "
        f"not wide-open robotic stare\n\n"
        f"This is the SAME PERSON as the input image — not a similar-looking person. "
        f"If it looks like a different person, regenerate.\n\n"
        f"Output: 9:16 portrait, photorealistic, full-frame, no text, no overlays."
    )


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY TEMPLATE — kept for backward compatibility with direct string formatting
# Use build_imagen_prompt() for new code.
# ─────────────────────────────────────────────────────────────────────────────

IMAGEN_PROMPT_TEMPLATE = """
Hyper-realistic smartphone photo of an everyday Indian woman, age {age}, {skin_tone} skin (hex {skin_hex}),
{face_shape} face. {hair}.
Wearing: {outfit}.
Accessories: {accessories_str}.
Distinguishing marks: {marks_str}.

Shot on an ordinary mid-range Android smartphone: slight overexposure on one side, no ring light,
no softbox, no studio lighting setup, natural slightly uneven exposure.
Skin tone: warm brown to medium brown — NOT fair, NOT light-skinned, NOT model-complexion.
Build: average, ordinary — NOT gym-fit, NOT model-thin, NOT aspirational.
Ultra-realistic skin texture with visible pores, no airbrushing, no beauty mode, no skin smoothing filter.

Expression: direct, slightly self-conscious eye contact with the camera lens — like someone about to say
something personal to a close friend, not performing for an audience.
Slight tension in the jaw or eyes suggesting they are about to share something real.
NOT smiling for a photo. NOT posing. Just present and honest.
Clothing looks lived-in, not brand new. Hair naturally styled at home, not salon-done.
Looks authentically like their stated occupation and life stage —
a housewife looks like she has been home all day,
an office worker looks like they just finished a long shift,
a student looks like they haven't slept enough.
Completely unretouched. Looks like a real person recording a UGC video at home.

Setting: {locked_background}

Camera: TIGHT MCU — chin to mid-chest only. Eye-level. The subject's hands and arms
are entirely outside the frame. Subject fills 70–80% of the frame vertically.

Format: 9:16 vertical portrait (1080×1920). Full frame edge to edge — no black bars,
no letterbox, no UI overlays, no subtitles, no watermarks.

Photorealistic, not illustrated. Skin has natural variation and imperfection.
Lighting: warm soft side-fill from the left (45°), secondary overhead ambient
fill to eliminate eye-socket shadows. Eyes clearly visible and sharp.
Cinematic contrast but warm and approachable — not harsh, not dramatic.
Ultra-sharp focus, 8k detail equivalent.
""".strip()
