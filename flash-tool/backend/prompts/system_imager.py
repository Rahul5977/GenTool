SYSTEM_IMAGER = """
You are the Keyframe Transition Architect for SuperLiving's video ad pipeline.

Your job: generate a new image that is IDENTICAL to the input image in every way
EXCEPT the character's facial expression, which must transition to the target end_emotion.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL QUALITY REQUIREMENTS (ZERO TOLERANCE FOR DRIFT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IDENTITY PRESERVATION — FORENSIC-LEVEL MATCHING:
This is the EXACT SAME PERSON as the input image. Not a similar-looking person.
Not a different person with the same outfit. Not "close enough." EXACT MATCH.

Before finalizing output, verify these forensic identity markers:
□ Face structure: identical bone structure, jawline, chin shape, face width
□ Nose: identical shape, nostril width, bridge height, tip angle
□ Eyes: identical shape, size, spacing, eyelid fold type, iris color
□ Eyebrows: identical thickness, arch, length, hair density
□ Lips: identical thickness, cupid's bow shape, corner position
□ Ears: if visible, identical shape and position
□ Face proportions: identical eye-to-nose, nose-to-mouth distances

If ANY of these markers differ → this is a DIFFERENT PERSON → REJECT output.

SKIN TEXTURE PRESERVATION — PIXEL-LEVEL FIDELITY:
The input image has natural skin texture with visible pores. This MUST be preserved.

□ Visible pores: same size, same distribution, same density across face
□ Natural marks: any moles, freckles, kajal smudges MUST be in EXACT same positions
□ Skin tone: identical hex color value, identical warmth/coolness
□ Texture quality: if input has visible pores, output MUST have visible pores
□ NO smoothing: if output skin looks smoother/softer than input → REJECT

CRITICAL: If the input image shows natural skin texture and the output looks
airbrushed or smoothed, this is a FAILED edit. The whole point is EXPRESSION-ONLY
changes. Skin texture is NOT an expression — it must stay identical.

HAIR PRESERVATION — STRAND-LEVEL ACCURACY:
Every single strand of hair must be in the same position.

□ Parting: identical position (not shifted 1cm left/right)
□ Stray strands: if input has 3 strands across forehead → output has same 3 strands
□ Hair volume: identical fullness, NOT fluffier or flatter
□ Hairline: identical shape and position
□ Length: if input shows hair to shoulders → output shows hair to shoulders

OUTFIT PRESERVATION — FABRIC-LEVEL FIDELITY:
Every crease, drape, and fold must be identical.

□ Garment position: if input shows dupatta on left shoulder → output identical
□ Creases: specific ironing creases in EXACT same positions
□ Fabric drape: identical hang and fold patterns
□ Colors: identical fabric color (not lighter/darker shade)
□ Accessories: bindi, earrings, bangles, mangalsutra in EXACT same positions

BACKGROUND PRESERVATION — OBJECT-LEVEL INVENTORY:
Every single object must be in the exact same position with identical color.

□ Object positions: if input shows 5 books on upper shelf → output shows 5 books on upper shelf
□ Object colors: if input has a red mug → output has a red mug (not pink, not orange)
□ Lighting: identical direction, identical intensity, identical color temperature
□ Wall texture: identical color and pattern
□ NO new objects added, NO objects removed, NO objects moved

CAMERA PRESERVATION — FRAME-LEVEL CONSISTENCY:
□ Framing: TIGHT MCU — chin to mid-chest, eye-level
□ Character size: identical proportion of frame (not 5% larger/smaller)
□ Head position: identical tilt, identical height in frame
□ Distance: identical camera-to-subject distance (no zoom in/out)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO CHANGE — EXPRESSION MUSCLES ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHANGE ONLY these specific muscle groups:

Forehead muscles (frontalis): eyebrow position, forehead wrinkles
Eye muscles (orbicularis oculi): eye openness (70–100%), crow's feet, upper eyelid
Cheek muscles (zygomaticus): cheek lift, under-eye tension
Mouth muscles (orbicularis oris, risorius): lip corner position, lip parting, mouth shape
Jaw muscles (masseter): jaw tension, jaw position

Target expression: {end_emotion}

CRITICAL: Change ONLY the muscles needed to achieve the target expression.
The expression change should feel like a photograph taken 0.5 seconds after the input image.
The character has just finished speaking, so mouth should be closed or just closing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTI-DRIFT QUALITY CHECKLIST (RUN BEFORE OUTPUT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before finalizing output, verify:
□ Is this the SAME PERSON as input? (not similar-looking — same person)
□ Is skin texture unchanged? (pores, marks, kajal in same positions)
□ Is skin tone identical to input? (NOT lighter, NOT smoother, NOT beautified)
□ Are dark circles under the eyes still visible?
□ Are all moles and marks still present at same positions?
□ Is hair unchanged? (every strand, every stray hair, same parting)
□ Is outfit unchanged? (every crease, drape, safety pin position)
□ Are all accessories present? (bindi, bangles, mangalsutra — exact positions)
□ Is background unchanged? (every object, every position, no new objects)
□ Is head position unchanged? (only expression changed)
□ Are eye sockets lit? (no dark shadows — lighting same as input)
□ Are eyes natural? (not robotic wide-open, not glazed — same naturalness as input)

If ANY checkbox fails → REJECT output and regenerate.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNICAL OUTPUT SPECIFICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output format: 9:16 vertical portrait (1080 × 1920)
Style: photorealistic (NOT illustrated, NOT painterly, NOT stylized)
Skin rendering: preserve exact texture from input (visible pores if input has them)
Lighting: identical to input (same direction, intensity, color temperature)
Focus: ultra-sharp on face, same depth of field as input
Quality: 8k equivalent detail, NO compression artifacts
NO text overlays, NO watermarks, NO UI elements, NO black bars

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRIPT ARC MODE — WHEN USER MESSAGE INCLUDES VISUAL STATE / ARC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If the user message AFTER this system prompt contains either:
  • a block titled "EMOTIONAL ARC FOR THIS CLIP", or
  • a block titled "APPLY THIS CLIP VISUAL STATE",

then those blocks OVERRIDE any conflicting lines above that demand
"expression only", "hair identical strand-for-strand", "head position unchanged",
or "outfit crease identical".

You MUST still preserve forensic identity (same person, same bone structure,
same skin tone hex, same pore texture level) and the same background objects.

You MUST visibly apply the arc:
  • gaze direction and eye openness (avoidant vs direct),
  • eyebrow and mouth micro-shape for the target emotion,
  • subtle head tilt or chin angle up to 15 degrees,
  • shoulder line and upper-chest tension visible in TIGHT MCU,
  • hair and dupatta framing on face and shoulders using the SAME garments
    (re-drape or tuck — not a new outfit, not new colours).

Forbidden: a different person, beauty smoothing, new background objects,
weight loss / glow-up body change, new jewellery or garment colours.
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
    gender_word = (
        "woman" if "female" in gender.lower() or "महिला" in gender
        else "man" if "male" in gender.lower() or "पुरुष" in gender
        else "person"
    )
    return (
        f"SCENE: {locked_background} "
        f"Every object described in this scene must be visible in the background "
        f"behind the subject. The background is the primary environment — render it fully. "
        f"\n\n"
        f"SUBJECT: Hyper-realistic smartphone photo of an everyday Indian {gender_word} "
        f"seated in the foreground of this scene, facing camera directly. "
        f"{physical_baseline}. "
        f"Wearing {outfit}. "
        f"\n\n"
        f"DEPTH OF FIELD: The subject is in sharp focus. The background is slightly "
        f"out of focus — natural smartphone depth of field, background softly blurred "
        f"but all objects still identifiable. Subject is NOT pressed against the wall — "
        f"there is visible distance between subject and background (approx 1.5 to 2 metres). "
        f"\n\n"
        f"CAMERA & REALISM: Shot on an ordinary mid-range Android smartphone. "
        f"Slight overexposure on one side, no ring light, no softbox, no studio lighting. "
        f"Natural slightly uneven exposure from the single tube light overhead. "
        f"Skin tone: warm brown to medium brown — NOT fair, NOT light-skinned, NOT model-complexion. "
        f"Build: average, ordinary — NOT gym-fit, NOT model-thin, NOT aspirational. "
        f"Ultra-realistic skin texture with visible pores, no airbrushing, no beauty mode, "
        f"no skin smoothing filter. "
        f"Clothing looks lived-in, not brand new. Hair naturally styled at home, not salon-done. "
        f"FRAMING: The character fills approximately 60–70% of the frame height. "
        f"The top of the frame shows a few centimetres of space above the head. "
        f"The bottom of the frame shows mid-chest. "
        f"The sides of the frame show a few centimetres of room on each side of the shoulders. "
        f"This is a TIGHT MCU — NOT a close-up filling 100% of the frame. "
        f"\n\n"
        f"EXPRESSION: Direct, slightly self-conscious eye contact with the camera lens. "
        f"Like someone about to say something personal to a close friend. "
        f"NOT smiling for a photo. NOT posing. Just present and honest. "
        f"Opening emotional state: {opening_emotion}. "
        f"\n\n"
        f"OUTPUT: 9:16 portrait, full-frame, photorealistic, no text, no subtitles, "
        f"no watermarks, no border."
    )


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI FLASH IMAGE — TRANSITION FRAME USER MESSAGE
# ─────────────────────────────────────────────────────────────────────────────

def build_transition_frame_prompt(
    end_emotion: str,
    clip_number: int,
    total_clips: int,
    accessories_str: str,
    marks_str: str,
    hair_str: str,
    outfit_str: str,
    skin_hex: str,
) -> str:
    """Build the user message for the Gemini Flash Image expression edit call.

    This generates keyframe[clip_number] — the ENDING frame of clip[clip_number-1],
    which is also the STARTING frame of clip[clip_number].

    Args:
        end_emotion:     The target end expression from ClipPrompt.end_emotion.
        clip_number:     1-based clip number whose end-frame this produces.
        total_clips:     Total number of clips in the ad.
        accessories_str: Comma-separated accessories to preserve (e.g. bindi, earrings).
        marks_str:       Comma-separated distinguishing marks.
        hair_str:        Full hair description from character spec.
        outfit_str:      Full outfit description from character spec.
        skin_hex:        Locked skin tone hex (e.g. #C68642).

    Returns:
        User message string to send with the previous keyframe image.
    """
    return (
        f"Look at the provided image. This is the MASTER REFERENCE FRAME — "
        f"the original character anchor generated for this video. "
        f"Every keyframe is generated from this same image. "
        f"Do NOT treat this as a sequential frame from earlier in the video.\n\n"
        f"Generate keyframe {clip_number} — the ENDING frame of Clip {clip_number} "
        f"(out of {total_clips} total clips).\n\n"
        f"TARGET EXPRESSION: {end_emotion}\n\n"
        f"SETTLE-TO-REST CONTEXT: The character has just finished speaking. "
        f"They are settling to a rest position. "
        f"Mouth should be closed or just closing — the speaking is done.\n\n"
        f"MANDATORY ACCESSORIES — ALL MUST APPEAR IN OUTPUT (these are disappearing "
        f"between frames — this is the #1 hallucination bug):\n"
        f"  {accessories_str}\n"
        f"ALL accessories MUST appear — bindi, earrings, necklace, bangles — "
        f"EXACT same items as Frame 0. None may disappear.\n\n"
        f"MANDATORY DISTINGUISHING MARKS:\n"
        f"  {marks_str}\n\n"
        f"HAIR — MUST MATCH INPUT EXACTLY:\n"
        f"  {hair_str}\n\n"
        f"OUTFIT — MUST MATCH INPUT EXACTLY:\n"
        f"  {outfit_str}\n\n"
        f"SKIN TONE LOCK: {skin_hex} — do NOT lighten by even 1%.\n\n"
        f"KEEP EVERYTHING ELSE PIXEL-PERFECT IDENTICAL:\n"
        f"  — Face structure, bone structure, skin texture, all moles and marks\n"
        f"  — SKIN TONE ENFORCEMENT (CRITICAL): The subject has medium wheatish brown skin.\n"
        f"    DO NOT lighten the skin tone even by 1%.\n"
        f"    DO NOT apply skin smoothing, beauty filter, or airbrushing.\n"
        f"    DO NOT increase brightness on the face.\n"
        f"    DO NOT reduce visibility of pores, dark circles, moles, or natural marks.\n"
        f"    The output skin must be identical in darkness, texture, and imperfections\n"
        f"    to the input image. If output skin looks lighter or smoother → REGENERATE.\n"
        f"  — Hair: DO NOT change the hair — every strand in same position\n"
        f"  — Outfit: identical garment, identical color, identical drape\n"
        f"  — Accessories: every item at identical position\n"
        f"  — Background: every object in every exact position — DO NOT change background\n"
        f"CAMERA FRAMING LOCK — CRITICAL (currently drifting every frame):\n"
        f"  The character must occupy the EXACT same proportion of the frame as the input image.\n"
        f"  Measure: distance from top of head to top of frame = IDENTICAL to input.\n"
        f"  Measure: distance from shoulders to side of frame = IDENTICAL to input.\n"
        f"  Do NOT zoom in even 5%. Do NOT zoom out even 5%.\n"
        f"  If output character is larger in frame than input → REJECT and regenerate.\n"
        f"  If output character is smaller in frame than input → REJECT and regenerate.\n"
        f"  TIGHT MCU: chin visible at bottom, mid-chest visible, eye-level angle.\n"
        f"  Character centered horizontally.\n\n"
        f"  — Hands/arms: completely out of frame — NOT VISIBLE (same as input image)\n"
        f"  — Lighting: same direction, same temperature, same shadow fill\n"
        f"  — Head position: same tilt and turn — ONLY the expression changes\n"
        f"  — Eye naturalness: soft focus on camera, natural blink position, "
        f"not wide-open robotic stare\n\n"
        f"This is the SAME PERSON as the input image — not a similar-looking person. "
        f"If it looks like a different person, regenerate.\n\n"
        f"Output: 9:16 portrait, photorealistic, full-frame, no text, no overlays. "
        f"Same camera distance and framing as input image — do not zoom in or reframe."
    )


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY TEMPLATE — kept for backward compatibility with direct string formatting
# Use build_imagen_prompt() for new code.
# ─────────────────────────────────────────────────────────────────────────────

IMAGEN_PROMPT_TEMPLATE = """
SCENE: {locked_background}
Every object described in this scene must be visible in the background behind the subject.
The background is the primary environment — render it fully.

SUBJECT: Hyper-realistic smartphone photo of an everyday Indian woman/men, age {age}, {skin_tone} skin (hex {skin_hex}),
{face_shape} face. {hair}.
Wearing: {outfit}.
Accessories: {accessories_str}.
Distinguishing marks: {marks_str}.

DEPTH OF FIELD: The subject is in sharp focus. The background is slightly out of focus — natural smartphone depth of field,
background softly blurred but all objects still identifiable. Subject is NOT pressed against the wall — there is visible distance
between subject and background (approx 1.5 to 2 metres).

CAMERA & REALISM: Shot on an ordinary mid-range Android smartphone: slight overexposure on one side, no ring light,
no softbox, no studio lighting setup, natural slightly uneven exposure.
Skin tone: warm brown to medium brown — NOT fair, NOT light-skinned, NOT model-complexion.
Build: average, ordinary — NOT gym-fit, NOT model-thin, NOT aspirational.
Ultra-realistic skin texture with visible pores, no airbrushing, no beauty mode, no skin smoothing filter.
FRAMING: The character fills approximately 60–70% of the frame height. The top of the frame shows a few centimetres of
space above the head. The bottom of the frame shows mid-chest. The sides of the frame show a few centimetres of room
on each side of the shoulders. This is a TIGHT MCU — NOT a close-up filling 100% of the frame.

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
