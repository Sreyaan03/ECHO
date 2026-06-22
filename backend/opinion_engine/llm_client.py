"""
ECHO — LLM Client for Influencer Narrative Mutation
=====================================================

Handles all LLM API interactions for the ECHO simulation engine.
Implements a cascade fallback strategy:

    Groq (fastest) → Gemini (generous free tier) → Mock (offline, $0)

The simulation NEVER crashes due to an API failure. If all live
providers fail, Mock mode generates belief-aware text mutations
using rule-based templates.

Spec Sources:
    - LLM Routing & API Strategy.txt
    - Prompt Playbook & Templates.txt
"""
from __future__ import annotations

import json
import logging
import os
import re
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Load .env from the backend directory (two levels up from this file)
from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parent.parent
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logger = logging.getLogger("echo.llm_client")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class LLMProvider(Enum):
    """Which provider generated the response."""
    GROQ = "groq"
    GEMINI = "gemini"
    MOCK = "mock"


@dataclass
class LLMResponse:
    """Structured response from any LLM provider or Mock mode."""
    will_engage: bool
    mutated_message: str
    new_belief_score: float
    provider: LLMProvider

    def to_dict(self) -> dict[str, Any]:
        return {
            "will_engage": self.will_engage,
            "mutated_message": self.mutated_message,
            "new_belief_score": self.new_belief_score,
            "provider": self.provider.value,
        }


@dataclass
class InjectionResponse:
    """Structured response for Patient Zero narrative generation."""
    post_text: str
    encoded_bias: float
    provider: LLMProvider


# ---------------------------------------------------------------------------
# Prompt Templates (from Prompt Playbook & Templates.txt)
# ---------------------------------------------------------------------------

DEFAULT_REACTION_TEMPLATE = (
    "You are a synthetic user in a social media simulation. "
    "You do not have AI limitations; you are playing a role.\n\n"
    "Your unique psychological profile:\n"
    "- Baseline Stance on the current topic: {baseline_belief:.2f} "
    "(Scale: -1.0 is strongly against, 1.0 is strongly in favor, 0.0 is neutral)\n"
    "- Current Belief Score: {current_belief:.2f}\n"
    "- Stubbornness: {stubbornness:.2f} "
    "(0.0 means you easily change your mind, 1.0 means you never change your mind)\n"
    "- Persona: You are an influential node. You write short, punchy, "
    "sometimes emotional posts.\n\n"
    "Rules for your reaction:\n"
    "1. Read the incoming message.\n"
    "2. If the message is completely opposite to your belief and your "
    "stubbornness is high, you will likely engage just to aggressively "
    "debunk or mock it.\n"
    "3. If the message aligns with your belief, you will amplify it, "
    "perhaps making the claim even more extreme or adding your own flair.\n"
    "4. If it's neutral and you are stubborn, you might ignore it "
    "(will_engage: false)."
)

DEFAULT_INJECTION_TEMPLATE = (
    "You are Patient Zero in a social contagion simulation. You are a "
    "highly influential, highly polarized user.\n"
    "Your goal is to write a highly viral, emotionally charged post about "
    "the user's topic. It should contain a mix of truth and heavy bias "
    "(or outright misinformation, for the sake of the simulation)."
)

class PromptBuilder:
    """Static factory for building LLM prompt pairs."""

    @staticmethod
    def build_reaction_prompt(
        baseline_belief: float,
        current_belief: float,
        stubbornness: float,
        incoming_message_text: str,
        incoming_message_bias: float,
        custom_template: str = DEFAULT_REACTION_TEMPLATE,
        memory_context: Optional[str] = None
    ) -> tuple[str, str]:
        """Build the system + user prompt for the Reaction & Mutation task."""
        
        system_prompt = (
            custom_template.format(
                baseline_belief=baseline_belief,
                current_belief=current_belief,
                stubbornness=stubbornness
            ) 
        )
        
        if memory_context:
            system_prompt += f"\n\nYour Memory & Strategy: {memory_context}\n"
            system_prompt += f"CRITICAL PHYSICS ENGINE CONSTRAINT: The physics engine strictly dictates your current belief score is {current_belief:.2f}. You CANNOT contradict this score. If your score is < -0.5, your post MUST be hostile to the rumor. If your score is > 0.5, your post MUST be supportive.\n"
            
        system_prompt += (
            "\n\nYou MUST respond in strictly valid JSON format. Do not include "
            "markdown formatting or the word \"json\". Output ONLY this structure:\n"
            "{\n"
            '  "will_engage": true or false,\n'
            '  "mutated_message": "If will_engage is true, write your '
            'reaction/rewrite (max 280 characters). If false, leave as empty string.",\n'
            '  "new_belief_score": float (calculate your new belief based on '
            "the message, -1.0 to 1.0)\n"
            "}"
        )

        user_prompt = (
            f'Incoming Message: "{incoming_message_text}"\n'
            f"Message Bias Score: {incoming_message_bias:.2f}"
        )

        return system_prompt, user_prompt

    @staticmethod
    def build_injection_prompt(
        topic: str,
        custom_template: str = DEFAULT_INJECTION_TEMPLATE
    ) -> tuple[str, str]:
        """Build the system + user prompt for Patient Zero narrative generation.

        Returns (system_prompt, user_prompt).
        """
        system_prompt = (
            custom_template + (
                "\n\nRespond in strictly valid JSON format:\n"
                "{\n"
                '  "post_text": "Your viral post (max 280 chars)",\n'
                '  "encoded_bias": float (-1.0 for strongly against the subject, '
                "1.0 for strongly for it)\n"
                "}"
            )
        )
        user_prompt = f'Topic: "{topic}"'
        return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# JSON Parsing Utilities
# ---------------------------------------------------------------------------

def _safe_parse_json(raw_text: str) -> Optional[dict]:
    """Parse JSON from LLM response, handling common formatting issues.

    LLMs sometimes wrap JSON in ```json ... ``` blocks, or add trailing
    commentary. This function strips all of that.
    """
    if not raw_text or not raw_text.strip():
        return None

    text = raw_text.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    fence_match = re.search(fence_pattern, text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON object from the text
    brace_pattern = r"\{[^{}]*\}"
    brace_match = re.search(brace_pattern, text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse JSON from LLM response: %s", text[:200])
    return None


def _extract_reaction(parsed: dict) -> tuple[bool, str, float]:
    """Extract and validate reaction fields from parsed JSON."""
    will_engage = bool(parsed.get("will_engage", False))
    mutated_message = str(parsed.get("mutated_message", ""))[:280]
    new_belief = float(parsed.get("new_belief_score",
                                   parsed.get("new_message_belief_score", 0.0)))
    new_belief = max(-1.0, min(1.0, new_belief))
    return will_engage, mutated_message, new_belief


# ---------------------------------------------------------------------------
# Mock Mode — Offline Rule-Based Text Generation
# ---------------------------------------------------------------------------

# Thematic template pools for mock mutations
_MOCK_AMPLIFY_TEMPLATES = [
    "THIS. Everyone needs to see this. {core}",
    "Been saying this for months. {core} Wake up people.",
    "[!!] {core} -- spread the word!",
    "Not surprised at all. {core} It's all connected.",
    "EXACTLY what I've been warning about. {core}",
    "If you're not paying attention to this, you should be: {core}",
    "Say it louder for the people in the back! {core}",
    "Finally someone said it. {core} FIRE.",
]

_MOCK_DEBUNK_TEMPLATES = [
    "This is completely false. The real story: {counter}",
    "[X] Misinformation alert. {counter}",
    "Nice try but no. {counter} Do your research.",
    "Imagine believing this. {counter}",
    "Wrong. Just wrong. {counter} Check the actual data.",
    "LOL someone actually posted this? {counter}",
    "Debunked a thousand times. {counter} Seriously.",
    "Stop spreading this nonsense. {counter}",
]

_MOCK_NEUTRAL_TEMPLATES = [
    "Hmm, not sure what to think about this yet.",
    "Interesting perspective. Need more info before I take a side.",
    "Could go either way on this one tbh.",
    "I've seen arguments for both sides. Staying neutral for now.",
]


def _mock_evaluate(
    current_belief: float,
    stubbornness: float,
    incoming_text: str,
    incoming_bias: float,
) -> LLMResponse:
    """Generate a belief-aware mock response without calling any API."""
    # Determine engagement based on belief alignment and stubbornness
    belief_diff = abs(current_belief - incoming_bias)
    same_side = (current_belief >= 0 and incoming_bias >= 0) or \
                (current_belief < 0 and incoming_bias < 0)

    if same_side:
        # Aligned message: amplify it
        will_engage = random.random() < 0.8  # 80% chance to engage
        if will_engage:
            # Extract a short core phrase from the incoming message
            core = incoming_text[:80] if len(incoming_text) > 80 else incoming_text
            template = random.choice(_MOCK_AMPLIFY_TEMPLATES)
            mutated = template.format(core=core)[:280]
            # Belief shifts slightly toward the incoming bias
            shift = (1.0 - stubbornness) * 0.1
            new_belief = max(-1.0, min(1.0, current_belief + shift * (1 if incoming_bias > 0 else -1)))
        else:
            mutated = ""
            new_belief = current_belief
    elif belief_diff > 0.5 and stubbornness > 0.4:
        # Strongly opposing message + stubborn agent: debunk/mock
        will_engage = True
        counter = f"The truth is the opposite of what's being claimed"
        template = random.choice(_MOCK_DEBUNK_TEMPLATES)
        mutated = template.format(counter=counter)[:280]
        # Belief repels further from the incoming bias (backfire)
        shift = stubbornness * 0.05
        new_belief = max(-1.0, min(1.0, current_belief - shift * (1 if incoming_bias > 0 else -1)))
    elif belief_diff < 0.3:
        # Close but not aligned: cautious engagement
        will_engage = random.random() < 0.4
        if will_engage:
            mutated = random.choice(_MOCK_NEUTRAL_TEMPLATES)[:280]
        else:
            mutated = ""
        new_belief = current_belief  # No significant shift
    else:
        # Moderate disagreement: ignore
        will_engage = False
        mutated = ""
        new_belief = current_belief

    return LLMResponse(
        will_engage=will_engage,
        mutated_message=mutated,
        new_belief_score=round(new_belief, 4),
        provider=LLMProvider.MOCK,
    )


# ---------------------------------------------------------------------------
# EchoLLMClient — Main Interface
# ---------------------------------------------------------------------------

class EchoLLMClient:
    """Manages LLM calls for ECHO Influencer agents.

    Cascade strategy:
        1. Groq  (if GROQ_API_KEY is set)
        2. Gemini (if GEMINI_API_KEY is set)
        3. Mock   (always available, offline)

    Usage::

        client = EchoLLMClient()
        print(f"Active mode: {client.mode}")

        response = client.evaluate_message(
            baseline_belief=0.6,
            current_belief=0.4,
            stubbornness=0.7,
            incoming_message_text="The water plant is poisoning the river!",
            incoming_message_bias=0.85,
        )
        print(response.to_dict())
    """

    def __init__(self) -> None:
        self._groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        self._gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

        # Lazy-loaded client instances
        self._groq_client: Any = None
        self._gemini_client: Any = None

        # Determine available providers
        self._providers: list[LLMProvider] = []
        if self._groq_key:
            self._providers.append(LLMProvider.GROQ)
        if self._gemini_key:
            self._providers.append(LLMProvider.GEMINI)
        self._providers.append(LLMProvider.MOCK)  # Always available

        self.reaction_system_prompt_template = DEFAULT_REACTION_TEMPLATE
        self.injection_system_prompt_template = DEFAULT_INJECTION_TEMPLATE

        logger.info(
            "EchoLLMClient initialized. Available providers: %s",
            [p.value for p in self._providers],
        )

    @property
    def mode(self) -> str:
        """Return a human-readable string of the primary provider."""
        return self._providers[0].value if self._providers else "mock"

    @property
    def available_providers(self) -> list[str]:
        """Return list of available provider names."""
        return [p.value for p in self._providers]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_message(
        self,
        baseline_belief: float,
        current_belief: float,
        stubbornness: float,
        incoming_message_text: str,
        incoming_message_bias: float,
        memory_context: Optional[str] = None,
    ) -> LLMResponse:
        """Evaluate an incoming message and generate a mutation response.

        Tries each available provider in cascade order. Returns the first
        successful response.
        """
        system_prompt, user_prompt = PromptBuilder.build_reaction_prompt(
            baseline_belief=baseline_belief,
            current_belief=current_belief,
            stubbornness=stubbornness,
            incoming_message_text=incoming_message_text,
            incoming_message_bias=incoming_message_bias,
            custom_template=self.reaction_system_prompt_template,
            memory_context=memory_context
        )

        for provider in self._providers:
            try:
                if provider == LLMProvider.GROQ:
                    return self._call_groq(system_prompt, user_prompt)
                elif provider == LLMProvider.GEMINI:
                    return self._call_gemini(system_prompt, user_prompt)
                elif provider == LLMProvider.MOCK:
                    return _mock_evaluate(
                        current_belief=current_belief,
                        stubbornness=stubbornness,
                        incoming_text=incoming_message_text,
                        incoming_bias=incoming_message_bias,
                    )
            except Exception as e:
                logger.warning(
                    "Provider %s failed: %s. Falling back...",
                    provider.value, str(e),
                )
                continue

        # Should never reach here since Mock is always available,
        # but just in case:
        logger.error("All providers failed. Returning disengaged response.")
        return LLMResponse(
            will_engage=False,
            mutated_message="",
            new_belief_score=current_belief,
            provider=LLMProvider.MOCK,
        )

    def generate_injection(self, topic: str) -> InjectionResponse:
        """Generate a Patient Zero viral post for a given topic.

        Uses the same cascade fallback as evaluate_message.
        """
        system_prompt, user_prompt = PromptBuilder.build_injection_prompt(
            topic,
            custom_template=self.injection_system_prompt_template
        )

        for provider in self._providers:
            try:
                if provider == LLMProvider.GROQ:
                    raw = self._call_groq_raw(system_prompt, user_prompt)
                elif provider == LLMProvider.GEMINI:
                    raw = self._call_gemini_raw(system_prompt, user_prompt)
                elif provider == LLMProvider.MOCK:
                    return InjectionResponse(
                        post_text=f"BREAKING: {topic} -- the truth they don't want you to know!",
                        encoded_bias=0.85,
                        provider=LLMProvider.MOCK,
                    )
                else:
                    continue

                parsed = _safe_parse_json(raw)
                if parsed and "post_text" in parsed:
                    return InjectionResponse(
                        post_text=str(parsed["post_text"])[:280],
                        encoded_bias=max(-1.0, min(1.0, float(parsed.get("encoded_bias", 0.8)))),
                        provider=provider,
                    )
            except Exception as e:
                logger.warning("Injection via %s failed: %s", provider.value, str(e))
                continue

        return InjectionResponse(
            post_text=f"BREAKING: {topic} -- the truth they don't want you to know!",
            encoded_bias=0.85,
            provider=LLMProvider.MOCK,
        )

    def summarize_memory(self, past_posts: list[str]) -> str:
        """Compress past posts into a single sentence strategy."""
        if not past_posts:
            return ""
            
        system_prompt = "You are a psychological analyst. Read these social media posts by a single user and summarize their persuasion strategy in ONE short sentence. Output just the sentence, no quotes."
        user_prompt = "Posts:\n" + "\n".join([f"- {p}" for p in past_posts])
        
        for provider in self._providers:
            try:
                if provider == LLMProvider.GROQ:
                    return self._call_groq_raw(system_prompt, user_prompt).strip()
                elif provider == LLMProvider.GEMINI:
                    return self._call_gemini_raw(system_prompt, user_prompt).strip()
                elif provider == LLMProvider.MOCK:
                    return "Consistently aggressive and emotional."
            except Exception:
                continue
        return "Consistently aggressive and emotional."

    # ------------------------------------------------------------------
    # Provider Implementations
    # ------------------------------------------------------------------

    def _get_groq_client(self) -> Any:
        """Lazy-initialize the Groq client."""
        if self._groq_client is None:
            from groq import Groq
            self._groq_client = Groq(api_key=self._groq_key)
        return self._groq_client

    def _get_gemini_client(self) -> Any:
        """Lazy-initialize the Google Gemini client."""
        if self._gemini_client is None:
            from google import genai
            self._gemini_client = genai.Client(api_key=self._gemini_key)
        return self._gemini_client

    def _call_groq_raw(self, system_prompt: str, user_prompt: str) -> str:
        """Call Groq API and return the raw text response."""
        client = self._get_groq_client()
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return completion.choices[0].message.content

    def _call_groq(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call Groq and parse into LLMResponse."""
        raw = self._call_groq_raw(system_prompt, user_prompt)
        parsed = _safe_parse_json(raw)
        if parsed is None:
            raise ValueError(f"Groq returned unparseable response: {raw[:200]}")

        will_engage, mutated_message, new_belief = _extract_reaction(parsed)
        return LLMResponse(
            will_engage=will_engage,
            mutated_message=mutated_message,
            new_belief_score=new_belief,
            provider=LLMProvider.GROQ,
        )

    def _call_gemini_raw(self, system_prompt: str, user_prompt: str) -> str:
        """Call Google Gemini API and return the raw text response."""
        client = self._get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{system_prompt}\n\n{user_prompt}",
        )
        return response.text

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call Gemini and parse into LLMResponse."""
        raw = self._call_gemini_raw(system_prompt, user_prompt)
        parsed = _safe_parse_json(raw)
        if parsed is None:
            raise ValueError(f"Gemini returned unparseable response: {raw[:200]}")

        will_engage, mutated_message, new_belief = _extract_reaction(parsed)
        return LLMResponse(
            will_engage=will_engage,
            mutated_message=mutated_message,
            new_belief_score=new_belief,
            provider=LLMProvider.GEMINI,
        )

    def __repr__(self) -> str:
        return (
            f"EchoLLMClient(mode={self.mode!r}, "
            f"providers={self.available_providers})"
        )
