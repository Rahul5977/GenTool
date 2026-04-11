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
        # Core subject
        f"Unretouched smartphone selfie of a real Indian {gender_word} at home. "
        f"NOT a professional photo. NOT a model. NOT studio-lit. "
        f"{physical_baseline}. Wearing {outfit}. "

        # Camera and lighting realism (prevents "perfect" renders)
        f"Shot on a mid-range Android phone (not iPhone): "
        f"slight overexposure on one side creating a natural hotspot, "
        f"uneven lighting from a single overhead tube light or window, "
        f"no ring light, no softbox, no professional lighting equipment, "
        f"natural grain and slight digital noise visible in shadows, "
        f"minor lens distortion typical of smartphone front cameras. "

        # Body type anti-aspiration (prevents model-like renders)
        f"Build: average everyday Indian body — NOT gym-fit, NOT model-proportioned, "
        f"NOT aspirational fitness-influencer physique. Ordinary, relatable build "
        f"that looks like a real person from Raipur, Patna, or Kanpur. "

        # Skin tone and texture (TRIPLE-LAYER anti-smoothing)
        f"Skin tone: warm brown to medium brown (#8B6F47 to #A0826D range) — "
        f"NOT fair/light-skinned (#C8AD8D or lighter), NOT model-complexion. "
        f"CRITICAL SKIN TEXTURE REQUIREMENTS (non-negotiable): "
        f"(1) Visible skin pores throughout face — zoom-level detail, not blurred away. "
        f"(2) Natural skin micro-texture with slight unevenness — NOT airbrushed smooth. "
        f"(3) Any natural marks, slight redness, or kajal smudges MUST be preserved. "
        f"(4) NO beauty mode processing. NO skin smoothing filter. NO blemish removal. "
        f"(5) NO Instagram-style soft-focus glow. NO makeup-ad perfect skin. "
        f"The face must look like a real person's skin when you zoom in, "
        f"with all the natural texture and imperfections intact. "

        # Hair and clothing realism
        f"Hair: naturally styled at home, NOT salon-done, NOT perfectly set. "
        f"A few stray strands across forehead or cheeks. Natural parting, not styled for a photoshoot. "
        f"Clothing: looks lived-in and worn, NOT brand new, NOT freshly ironed. "
        f"Slight creases from wearing throughout the day. Authentic home-wear texture. "

        # Expression and demeanor
        f"Expression: {opening_emotion}. "
        f"Direct eye contact with the camera lens — like someone about to record "
        f"a personal video message to a close friend, NOT posing for a professional portrait. "
        f"Slight self-consciousness in the eyes or jaw tension suggesting they're about "
        f"to share something real and vulnerable, NOT performing for an audience. "
        f"NOT smiling for a photo op. NOT Instagram-ready pose. Just present, honest, unfiltered. "

        # Background
        f"Background: {locked_background} "
        f"This is a real Tier 2-3 Indian home, NOT a modern metro apartment. "
        f"Slightly worn walls, simple furniture, ordinary lighting. "

        # Camera and framing
        f"HANDS AND ARMS: completely outside the frame — NOT VISIBLE at all. "
        f"Tight medium close-up shot (TIGHT MCU): chin to mid-chest only, eye-level, camera absolutely still. "
        f"Subject fills 70-80% of the frame vertically. "

        # Final quality markers
        f"Overall aesthetic: looks exactly like a high-trust UGC video screenshot — "
        f"the kind a real person would record at home to share their story. "
        f"NOT a professional advertisement. NOT a beauty/fashion shoot. "
        f"NOT AI-generated-looking perfection. Real, unpolished, authentic human presence. "

        # Technical output specs
        f"Output format: 9:16 vertical portrait (1080x1920), photorealistic rendering, "
        f"ultra-sharp focus on face with natural depth of field blur in background. "
        f"NO text, NO watermarks, NO UI elements, NO black letterbox bars."
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
        f"  — Hands/arms: completely out of frame — NOT VISIBLE (same as input image)\n"
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
Hyper-realistic smartphone photo of an everyday Indian woman/men, age {age}, {skin_tone} skin (hex {skin_hex}),
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
