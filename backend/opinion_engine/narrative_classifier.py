import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional
from opinion_engine.religion_registry import ReligionRegistry

logger = logging.getLogger("echo.narrative_classifier")

@dataclass
class NarrativeProfile:
    topic_index: int
    topic_name: str
    initial_belief_valence: float
    group_sensitivity: Dict[str, float]         # Keyed by religion name
    class_sensitivity: Dict[str, float]         # Keyed by economic class name
    initial_arousal_spike: float


def _build_grounded_system_prompt(
    registry: ReligionRegistry,
    economic_registry: Optional[object] = None,
) -> str:
    """
    Builds a rich system prompt that injects the full cultural model from
    religions.json as context. The LLM reasons OVER our data, not from scratch.
    """

    # --- Topic Descriptions ---
    # Explain to the LLM what each topic category actually means in the
    # Indian sociological context, grounding it beyond just a label.
    topic_descriptions = {
        "Secular / Political": (
            "Deals with governance, elections, nationalism, secularism vs. religious identity "
            "in the state. Examples: voting along religious lines, CAA/NRC, Article 370."
        ),
        "Dietary Laws": (
            "Deals with food, cattle slaughter, halal/jhatka, beef/pork bans, and food "
            "identity in India. Highly charged between Hindus (cow reverence) and Muslims "
            "(halal, beef consumption)."
        ),
        "Conversion / Apostasy": (
            "Deals with religious conversion, anti-conversion laws (e.g. Ghar Wapsi), "
            "Christian missionaries, love jihad conspiracy theories, and apostasy."
        ),
        "Minority Rights": (
            "Deals with rights of religious minorities, hijab bans, temple-mosque disputes, "
            "Uniform Civil Code, affirmative action for minorities, and civil liberties "
            "framed through a religious lens."
        ),
        "Sacred Symbols / Worship": (
            "Deals with symbols of religious identity: the hijab, the tilak, azaan, "
            "religious processions, temple entries, loudspeaker bans, and desecration of "
            "holy sites or idols."
        ),
    }

    # --- Per-religion Contextual Profiles ---
    # For each religion, build a rich description of what they care about,
    # referencing their dogma vector and friction scores from the JSON data.
    religion_profiles = []
    for i, name in enumerate(registry.names):
        profile = registry.profiles[i]
        dogma = profile.dogma_vector  # list of floats aligned with topic_categories
        authority = profile.authority_multiplier
        gull_lo, gull_hi = profile.base_gullibility_range

        # Build a per-topic dogma breakdown
        topic_lines = []
        for t_idx, t_name in enumerate(registry.topic_categories):
            score = dogma[t_idx]
            if score >= 0.8:
                rigidity = "extremely dogmatic (will fiercely resist information contradicting their stance)"
            elif score >= 0.6:
                rigidity = "highly dogmatic (strong emotional reaction, low openness)"
            elif score >= 0.4:
                rigidity = "moderately dogmatic (engaged but persuadable)"
            elif score >= 0.2:
                rigidity = "mildly sensitive (aware but mostly open)"
            else:
                rigidity = "largely indifferent (topic has little emotional pull)"
            topic_lines.append(f"    - {t_name} (score={score:.1f}): {rigidity}")

        # Build friction profile with other groups
        friction_lines = []
        for j, other_name in enumerate(registry.names):
            if i == j:
                continue
            friction_val = registry.friction_matrix[i][j]
            if friction_val >= 0.5:
                friction_desc = "high animosity"
            elif friction_val >= 0.3:
                friction_desc = "moderate tension"
            elif friction_val >= 0.1:
                friction_desc = "mild wariness"
            else:
                friction_desc = "largely neutral"
            friction_lines.append(f"    - vs {other_name}: {friction_desc} (friction={friction_val:.2f})")

        religion_profiles.append(
            f"### {name}\n"
            f"  - Authority of religious leaders: {authority:.1f}x (higher = clerics dominate group belief)\n"
            f"  - Openness to persuasion: low={gull_lo}, high={gull_hi} (lower = more stubborn)\n"
            f"  - Dogma by topic:\n" + "\n".join(topic_lines) + "\n"
            f"  - Inter-group friction:\n" + "\n".join(friction_lines)
        )

    topic_reference = "\n".join(
        [f"  {i}: \"{t}\" — {topic_descriptions.get(t, '')}"
         for i, t in enumerate(registry.topic_categories)]
    )

    # --- Economic Class Context -------------------------------------------
    # Inject class profiles so the LLM can reason about class-level sensitivity.
    # Only included when an EconomicRegistry is loaded.
    econ_section = ""
    class_schema_line = ""
    class_names_for_schema = []
    if economic_registry is not None:
        class_lines = []
        for cls in economic_registry.profiles:
            class_lines.append(
                f"  - {cls.name} (anxiety_multiplier={cls.economic_anxiety_multiplier:.2f}, "
                f"literacy={cls.base_literacy_range[0]:.1f}–{cls.base_literacy_range[1]:.1f}, "
                f"political_lean_bias={cls.political_lean_bias:+.1f}): "
                f"{cls.authority_figure}"
            )
            class_names_for_schema.append(cls.name)
        econ_section = (
            "\n### Economic Classes (Guy Standing Precariat Model)\n"
            + "\n".join(class_lines)
            + "\n\nFor each class, estimate how reactive they will be to this rumor "
            "(0.0 = indifferent, 1.0 = maximally agitated). "
            "Use the anxiety_multiplier as a strong prior: Precariat (0.95) will almost "
            "always be highly reactive to economically threatening narratives, "
            "while the Elite (0.10) will rarely be emotionally provoked."
        )
        class_names_json = "\n    ".join(
            [f'"{name}": <float 0.0 to 1.0>,' for name in class_names_for_schema]
        )
        class_schema_line = f',\n  "class_sensitivity": {{\n    {class_names_json}\n  }}'

    system_prompt = f"""You are a precision sociological classifier for an Indian social dynamics simulation.

You will receive a rumor, news story, or social narrative. Your job is to classify it using the EXACT cultural model defined below and return a JSON object.

---
## YOUR CULTURAL MODEL (Ground Truth — reason from THIS, not your general knowledge)

### Topic Categories
{topic_reference}

### Group Profiles
{chr(10).join(religion_profiles)}
{econ_section}
---
## YOUR TASK

Given the rumor, you must determine:

1. **topic_index**: Which of the 5 topic categories does this rumor primarily activate? Use the group dogma scores above as your guide — the topic where the highest-dogma group is most triggered is usually the correct one.

2. **initial_belief_valence**: Is the rumor framed positively (+1.0) or negatively (-1.0) toward the dominant religious majority (Hindu)? 0.0 = neutral framing.

3. **group_sensitivity**: For EACH religion group, how emotionally reactive will they be to this specific rumor? 
   - Derive this from each group's dogma score on the classified topic.
   - Modulate by the rumor's directness toward that group.
   - A rumor directly attacking a group's core dogma should score near their dogma value.
   - A rumor irrelevant to a group should score near 0.1.

4. **class_sensitivity** *(if economic classes listed above)*: For EACH economic class, how reactive will they be? Use anxiety_multiplier as a prior.

5. **initial_arousal_spike**: How viral is this rumor at first contact? Consider how many groups are simultaneously provoked and how high the inter-group friction is between them.

Return ONLY this JSON, no explanation:
{{
  "topic_index": <integer 0-{len(registry.topic_categories) - 1}>,
  "initial_belief_valence": <float -1.0 to 1.0>,
  "group_sensitivity": {{
    {chr(10).join([f'    "{name}": <float 0.0 to 1.0>,' for name in registry.names])}
  }}{class_schema_line},
  "initial_arousal_spike": <float 0.0 to 1.0>
}}"""

    return system_prompt


async def classify_narrative(
    text: str,
    registry: ReligionRegistry,
    economic_registry: Optional[object] = None,
) -> NarrativeProfile:
    """
    Calls the LLM once at initialization to compile the rumor into a mathematical profile.
    The system prompt is grounded in the full religions.json (and optionally economics.json)
    cultural models so the LLM reasons over our curated data, not from scratch.
    """
    if not text or not text.strip():
        return _get_default_profile(registry, economic_registry)

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        logger.warning("No GROQ_API_KEY found. Falling back to default narrative profile.")
        return _get_default_profile(registry, economic_registry)

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=groq_key)

        system_prompt = _build_grounded_system_prompt(registry, economic_registry)

        logger.info(f"Classifying narrative: '{text[:80]}...'")

        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'Rumor: "{text}"'}
            ],
            model="llama-3.3-70b-versatile",  # Current recommended Groq model for reasoning
            temperature=0.0,           # Deterministic — we want consistent classification
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)
        logger.info(f"LLM classified narrative: {parsed}")

        # Validation & clamping
        topic_idx = int(parsed.get("topic_index", 0))
        if topic_idx < 0 or topic_idx >= len(registry.topic_categories):
            topic_idx = 0

        sensitivities = {}
        raw_sens = parsed.get("group_sensitivity", {})
        for r in registry.names:
            raw = float(raw_sens.get(r, 0.3))
            sensitivities[r] = max(0.0, min(1.0, raw))  # clamp to [0, 1]

        # Parse class_sensitivity if economic registry is present
        class_sensitivities: Dict[str, float] = {}
        if economic_registry is not None:
            raw_class_sens = parsed.get("class_sensitivity", {})
            for cls in economic_registry.profiles:
                raw = float(raw_class_sens.get(cls.name, cls.economic_anxiety_multiplier))
                class_sensitivities[cls.name] = max(0.0, min(1.0, raw))
        else:
            class_sensitivities = {}

        valence = float(parsed.get("initial_belief_valence", 0.0))
        valence = max(-1.0, min(1.0, valence))

        arousal = float(parsed.get("initial_arousal_spike", 0.3))
        arousal = max(0.0, min(1.0, arousal))

        return NarrativeProfile(
            topic_index=topic_idx,
            topic_name=registry.topic_categories[topic_idx],
            initial_belief_valence=valence,
            group_sensitivity=sensitivities,
            class_sensitivity=class_sensitivities,
            initial_arousal_spike=arousal
        )

    except Exception as e:
        logger.error(f"Failed to classify narrative via LLM: {e}. Falling back to default profile.")
        return _get_default_profile(registry, economic_registry)


def _get_default_profile(
    registry: ReligionRegistry,
    economic_registry: Optional[object] = None,
) -> NarrativeProfile:
    sensitivities = {r: 0.3 for r in registry.names}
    class_sensitivities: Dict[str, float] = {}
    if economic_registry is not None:
        class_sensitivities = {
            cls.name: cls.economic_anxiety_multiplier
            for cls in economic_registry.profiles
        }
    return NarrativeProfile(
        topic_index=0,
        topic_name=registry.topic_categories[0] if registry.topic_categories else "Unknown",
        initial_belief_valence=0.0,
        group_sensitivity=sensitivities,
        class_sensitivity=class_sensitivities,
        initial_arousal_spike=0.3
    )
