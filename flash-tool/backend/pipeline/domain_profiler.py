"""Domain Profiler — maps health domains to visual appearance markers.

Every domain has two visual states: pre-coach (problem displayed) and post-coach
(confidence displayed). The PHYSICAL BODY never changes — only BEHAVIOUR and STYLING
change. This is critical because Veo blocks medical transformation language.

Usage:
    from backend.pipeline.domain_profiler import get_domain_profile, build_visual_states

    profile = get_domain_profile("weight")
    visual_states = build_visual_states(profile, num_clips=6, coach_clip=3)
"""

from ..models import DomainProfile, VisualState

# ═══════════════════════════════════════════════════════════════
# DOMAIN REGISTRY
# ═══════════════════════════════════════════════════════════════
# CRITICAL: Every term here MUST be Veo-safe. NEVER use medical terms.
# We describe WHAT THE CAMERA SEES (behaviour, posture, styling),
# NOT medical diagnoses.

_DOMAIN_PROFILES: dict[str, DomainProfile] = {
    "weight": DomainProfile(
        domain="weight",
        pre_coach_appearance_modifiers=[
            "fuller build, round face with soft full cheeks",
            "loose oversized cotton kurta draped wide to cover body",
            "dupatta wrapped around shoulders and chest as a shield",
            "slightly heavy upper arms visible through loose fabric",
            "body language of someone who avoids being photographed",
        ],
        post_coach_appearance_modifiers=[
            "same build, same face — NO weight change visible",
            "same kurta now worn naturally, not hiding behind it",
            "dupatta pinned neatly to one shoulder — body visible",
            "sitting/standing taller, chest open, owning the frame",
            "body language of someone who just stopped caring what others think",
        ],
        pre_coach_visual_states={
            "posture": "slight slouch, shoulders rolled forward 10-15°, chin tucked down, body compressed inward as if trying to take less space",
            "styling": "hair falling over face partially, dupatta pulled across chest as shield, hiding body contour",
            "energy": "low",
            "eye_contact": "avoidant",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "upright, shoulders back and relaxed, chin level, body open and taking natural space in frame",
            "styling": "hair tucked behind one ear showing full face, dupatta pinned neatly to left shoulder, body visible and not hidden",
            "energy": "high",
            "eye_contact": "warm_direct",
            "voice": "warm_confident",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[
            "fuller build with round face and soft full cheeks",
            "slightly heavy frame — NOT model-thin, NOT gym-fit",
            "natural Indian woman from Tier 2 city, average body type",
            "loose cotton kurta draped wide",
        ],
    ),
    "skin": DomainProfile(
        domain="skin",
        pre_coach_appearance_modifiers=[
            "natural uneven skin texture on cheeks and forehead — visible pores, natural imperfections",
            "no makeup, raw bare face — the face of someone who stopped trying",
            "slight dark circles from disrupted sleep",
            "hair falling over sides of face, partially hiding cheeks",
            "less kajal, no bindi — not putting effort into appearance",
        ],
        post_coach_appearance_modifiers=[
            "same skin texture — NO clear skin transformation shown",
            "light kajal applied, small red bindi back on forehead",
            "hair tucked behind ears — face fully visible and owned",
            "face positioned to catch more warm light naturally",
            "body language of someone who looks in the mirror again",
        ],
        pre_coach_visual_states={
            "posture": "slight forward hunch, chin tilted down, avoiding full-face camera angle",
            "styling": "hair loose and falling over face to hide cheeks, no makeup, no accessories — given up on appearance",
            "energy": "low",
            "eye_contact": "avoidant",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "head level, chin up naturally, comfortable with face being fully visible to camera",
            "styling": "hair tucked behind ears, light kajal, small bindi — small daily effort that signals self-care returning",
            "energy": "medium",
            "eye_contact": "direct",
            "voice": "conversational",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[
            "natural imperfect skin — visible pores, slightly uneven skin tone, NO airbrushing",
            "bare face, no makeup, no kajal — the raw natural look of someone who stopped trying",
            "NOT model skin, NOT photoshoot skin — real Tier 2 city woman's face",
        ],
    ),
    "stress": DomainProfile(
        domain="stress",
        pre_coach_appearance_modifiers=[
            "subtle dark circles under eyes — the face of someone who doesn't sleep well",
            "tense jaw, slightly clenched — visible muscle tension",
            "shoulders raised and tight, not relaxed",
            "fidgeting with dupatta edge between fingers",
            "eyes slightly squinted, forehead micro-wrinkled from constant tension",
        ],
        post_coach_appearance_modifiers=[
            "same face — dark circles still there but eyes more open and present",
            "jaw visibly relaxed, mouth resting naturally",
            "shoulders dropped to natural position, not raised",
            "hands still in lap, no fidgeting",
            "forehead smooth, eyes at natural openness",
        ],
        pre_coach_visual_states={
            "posture": "tense upright, shoulders raised toward ears, jaw clenched, body rigid — the posture of someone carrying invisible weight",
            "styling": "dupatta twisted/fidgeted with between fingers, hair slightly unkempt, accessories minimal — appearance is afterthought",
            "energy": "low",
            "eye_contact": "intermittent",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "relaxed upright, shoulders dropped naturally, jaw soft, body settled — someone who learned to exhale",
            "styling": "dupatta draped calmly, hair neatened, small bindi back — small signals of re-engagement with self",
            "energy": "medium",
            "eye_contact": "direct",
            "voice": "conversational",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[
            "tense facial muscles, slightly squinted eyes, raised shoulders",
            "the face and body of someone under constant invisible pressure",
            "NOT relaxed, NOT serene — visibly carrying stress in body",
        ],
    ),
    "muscle": DomainProfile(
        domain="muscle",
        pre_coach_appearance_modifiers=[
            "slim frame — kurta/shirt hanging loose on thin shoulders",
            "slightly sunken cheeks, face looks thinner than average",
            "wrists and forearms visible — naturally thin build",
            "low energy in posture — the body of someone who feels physically inadequate",
            "clothes look oversized because frame is narrow, not because clothes are large",
        ],
        post_coach_appearance_modifiers=[
            "same thin frame — NO muscle gain visible",
            "same clothes, but sitting/standing taller with chin up",
            "posture improved dramatically — from defeated to determined",
            "more animated facial expressions, eyes more open",
            "body language of someone who started showing up for themselves",
        ],
        pre_coach_visual_states={
            "posture": "slight slouch, shoulders narrow and forward, body taking minimum space — the posture of physical self-doubt",
            "styling": "shirt/kurta hanging loose on thin frame, sleeves slightly too wide — clothes chosen to hide, not to fit",
            "energy": "low",
            "eye_contact": "avoidant",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "upright with shoulders pulled back, chin up, chest open — the same thin frame but owned confidently",
            "styling": "same clothes but worn with intention — sleeves pushed up slightly, posture making them fit better",
            "energy": "high",
            "eye_contact": "direct",
            "voice": "warm_confident",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[
            "slim build, narrow shoulders, shirt hanging loose on thin frame",
            "NOT muscular, NOT gym-fit — naturally thin Indian man from small city",
            "the build of someone who wants to be stronger but isn't yet",
        ],
    ),
    "sexual": DomainProfile(
        domain="sexual",
        pre_coach_appearance_modifiers=[
            "nervous energy visible — slight restlessness in body",
            "avoiding direct camera gaze — eyes darting or looking down",
            "hair/dupatta used as psychological shield — hiding behind it",
            "body slightly turned away from camera — not fully facing it",
            "the body language of someone sharing something deeply private",
        ],
        post_coach_appearance_modifiers=[
            "calm settled energy — body at rest, no restlessness",
            "direct natural eye contact — comfortable being seen",
            "dupatta draped normally, hair not used as shield",
            "body fully facing camera — open, not hiding",
            "the body language of someone who found out they're not alone",
        ],
        pre_coach_visual_states={
            "posture": "body slightly turned 5-10° away from camera, shoulders guarded, hands clasped tight — the posture of someone about to share a secret",
            "styling": "dupatta held close to face, hair falling forward as curtain — creating physical barriers between self and camera",
            "energy": "low",
            "eye_contact": "avoidant",
            "voice": "whisper",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "body squarely facing camera, shoulders relaxed and open, hands at rest — the posture of someone who stopped being ashamed",
            "styling": "dupatta draped naturally, hair tucked back, face fully visible — barriers removed",
            "energy": "medium",
            "eye_contact": "direct",
            "voice": "conversational",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[
            "guarded body language — shoulders turned slightly, not fully facing camera",
            "the look of someone about to say something they've never told anyone",
            "nervous energy visible in posture",
        ],
    ),
    "hairloss": DomainProfile(
        domain="hairloss",
        pre_coach_appearance_modifiers=[
            "thin hair at center parting — visible scalp line wider than normal",
            "hair flat against scalp, lightly oiled, lacking volume",
            "pallu/dupatta occasionally positioned to cover hairline",
            "forehead partially hidden by how hair is arranged",
            "the hair of someone who avoids mirrors and cameras",
        ],
        post_coach_appearance_modifiers=[
            "same hair thickness — NO miraculous hair growth shown",
            "hair slightly better styled — small effort visible",
            "forehead visible — not hiding the hairline anymore",
            "dupatta used normally, not as scalp cover",
            "the hair of someone who stopped obsessing and started living",
        ],
        pre_coach_visual_states={
            "posture": "head slightly angled to camera to minimize hairline visibility, chin tucked",
            "styling": "hair arranged to maximum coverage, pallu positioned near head, self-conscious about top-of-head angle",
            "energy": "low",
            "eye_contact": "intermittent",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "head level and natural, not angled to hide anything, comfortable with camera above eye level",
            "styling": "hair simply styled but not obsessively arranged for coverage, forehead naturally visible",
            "energy": "medium",
            "eye_contact": "direct",
            "voice": "conversational",
            "lighting": "neutral",
        },
        imagen_character_modifiers=[
            "thin hair at center parting, visible scalp line, flat against head",
            "NOT thick luscious hair — the natural thinning of a real person",
            "hair lightly oiled, lacking body and volume",
        ],
    ),
    "energy": DomainProfile(
        domain="energy",
        pre_coach_appearance_modifiers=[
            "eyelids heavy at ~60% open — the perpetually tired look",
            "face lacking animation — minimal microexpressions",
            "body leaning back, low-effort posture",
            "speech noticeably slower, pauses between phrases",
            "the entire bearing of someone running on empty",
        ],
        post_coach_appearance_modifiers=[
            "eyelids at natural ~80% open — alert and present",
            "face more animated — eyebrows move, expressions shift naturally",
            "slight forward lean — engaged with the conversation",
            "normal speech pace, natural rhythm",
            "the bearing of someone who remembered what energy feels like",
        ],
        pre_coach_visual_states={
            "posture": "leaning back, body weight sinking into seat, shoulders drooped, minimal effort in sitting upright — the posture of chronic exhaustion",
            "styling": "appearance low-effort — minimal accessorizing, hair just functional not styled, clothes wearing the person instead of person wearing clothes",
            "energy": "low",
            "eye_contact": "intermittent",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "slight forward lean, shoulders naturally positioned, body engaged and present — the posture of someone who has fuel in the tank again",
            "styling": "small improvements — bindi on, earrings visible, hair slightly better arranged — the minimum viable self-care",
            "energy": "high",
            "eye_contact": "warm_direct",
            "voice": "warm_confident",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[
            "heavy eyelids, tired face, low-energy posture — leaning back",
            "the face and body of someone who is exhausted before the day starts",
            "NOT sick-looking — just perpetually drained",
        ],
    ),
    "general": DomainProfile(
        domain="general",
        pre_coach_appearance_modifiers=[
            "body language of someone carrying an unnamed burden",
            "less effort in appearance — functional, not intentional",
            "slightly withdrawn posture",
        ],
        post_coach_appearance_modifiers=[
            "same person, but posture open and confident",
            "small grooming improvements — bindi, kajal, hair tidied",
            "body language of someone found support",
        ],
        pre_coach_visual_states={
            "posture": "slight slouch, closed-off body language, taking less space",
            "styling": "functional appearance, minimal effort, nothing intentional",
            "energy": "low",
            "eye_contact": "intermittent",
            "voice": "low",
            "lighting": "cooler_single_source",
        },
        post_coach_visual_states={
            "posture": "upright, open body language, comfortable in own space",
            "styling": "small grooming improvements visible — bindi, kajal, hair arranged",
            "energy": "medium",
            "eye_contact": "direct",
            "voice": "conversational",
            "lighting": "warmer_positioned",
        },
        imagen_character_modifiers=[],
    ),
}

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "weight": ["moti", "mota", "dheele kapde", "weight", "pet", "tond", "wazan", "bharee", "fit nahi", "size", "kapde nahi aate", "XL", "XXL", "loose kapde"],
    "skin": ["daane", "daana", "muhase", "chehra", "face", "skin", "glow", "cream", "serum", "retinol", "niacinamide", "oily", "chikna", "dark spots", "dhabba"],
    "stress": ["tension", "stress", "neend nahi", "insomnia", "anxiety", "pareshan", "dar", "panic", "overthink", "soch", "restless"],
    "muscle": ["patla", "dubla", "body nahi bani", "gym", "protein", "muscle", "weak", "kamzor", "strength", "dole"],
    "sexual": ["sex", "performance", "stamina", "nightfall", "shighrapatan", "erectile", "libido", "mardangi", "timing"],
    "hairloss": ["baal", "hair", "jhad", "ganja", "thinning", "hair fall", "baalon ka", "sar pe"],
    "energy": ["thakan", "energy", "tired", "sust", "aalas", "neend", "3 baje", "utha nahi jaata", "zor nahi"],
}


def get_domain_profile(domain: str) -> DomainProfile:
    """Get the DomainProfile for a given domain string. Falls back to 'general'."""
    return _DOMAIN_PROFILES.get(domain.lower(), _DOMAIN_PROFILES["general"])


def detect_domain(script: str) -> str:
    """Auto-detect the health domain from script text using keyword matching."""
    script_lower = script.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in script_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"

    return max(scores, key=scores.get)


def build_visual_states(
    profile: DomainProfile,
    num_clips: int,
    coach_clip: int,
) -> list[VisualState]:
    """Generate one VisualState per clip with a pre->post coach arc."""
    pre = profile.pre_coach_visual_states
    post = profile.post_coach_visual_states

    states: list[VisualState] = []
    for clip_num in range(1, num_clips + 1):
        if clip_num < coach_clip:
            states.append(VisualState(
                posture=pre["posture"],
                styling_state=pre["styling"],
                energy_level=pre["energy"],
                eye_contact_pattern=pre["eye_contact"],
                voice_register=pre["voice"],
                lighting_warmth=pre["lighting"],
            ))
        elif clip_num == coach_clip:
            states.append(VisualState(
                posture=f"TRANSITIONING: {pre['posture']} → beginning to shift — chin lifts slightly, first sign of openness. Not yet at post-coach posture.",
                styling_state=pre["styling"],
                energy_level="medium",
                eye_contact_pattern="intermittent",
                voice_register="conversational",
                lighting_warmth="neutral",
            ))
        else:
            clips_after_coach = num_clips - coach_clip
            clip_offset = clip_num - coach_clip
            progress = clip_offset / max(clips_after_coach, 1)

            if progress < 0.5:
                states.append(VisualState(
                    posture=f"BUILDING: {post['posture']} — noticeably straighter than pre-coach but not yet fully confident.",
                    styling_state=f"FIRST CHANGES: small improvements visible — {post['styling'].split(',')[0] if ',' in post['styling'] else post['styling']}",
                    energy_level="medium",
                    eye_contact_pattern="direct",
                    voice_register="conversational",
                    lighting_warmth="neutral",
                ))
            else:
                states.append(VisualState(
                    posture=post["posture"],
                    styling_state=post["styling"],
                    energy_level=post["energy"],
                    eye_contact_pattern=post["eye_contact"],
                    voice_register=post["voice"],
                    lighting_warmth=post["lighting"],
                ))

    return states


def detect_coach_clip(clips: list, num_clips: int) -> int:
    """Detect which clip introduces the coach based on dialogue content."""
    coach_keywords = ["coach", "SuperLiving", "super living", "superliving", "Rishika", "Rashmi", "Seema", "Pankaj", "app pe", "app par", "baat hui", "baat ki"]

    for clip in clips:
        dialogue = getattr(clip, "dialogue", "") if hasattr(clip, "dialogue") else str(clip)
        for keyword in coach_keywords:
            if keyword.lower() in dialogue.lower():
                clip_num = getattr(clip, "clip_number", None)
                if clip_num:
                    return clip_num

    return min(3, (num_clips + 1) // 2)
