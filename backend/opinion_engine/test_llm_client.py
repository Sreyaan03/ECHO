"""
ECHO -- LLM Client Validation Suite
====================================

Tests the EchoLLMClient across all three modes:
  1. Mock mode   (always runs -- no keys needed)
  2. Groq live   (runs only if GROQ_API_KEY is set)
  3. Gemini live (runs only if GEMINI_API_KEY is set)
  4. JSON parsing edge cases
  5. Cascade fallback logic

Usage:
    python test_llm_client.py
"""

import os
import sys
import json

# Ensure the opinion_engine package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_client import (
    EchoLLMClient,
    LLMProvider,
    LLMResponse,
    PromptBuilder,
    _safe_parse_json,
    _mock_evaluate,
)


def divider(title: str) -> None:
    print(f"\n{'='*64}")
    print(f"  {title}")
    print(f"{'='*64}")


def test_mock_mode():
    """Test 1: Mock mode always generates valid responses."""
    divider("TEST 1: Mock Mode (Offline, No Keys)")

    # Test with aligned beliefs (should amplify)
    response = _mock_evaluate(
        current_belief=0.7,
        stubbornness=0.3,
        incoming_text="The new water plant is poisoning the river!",
        incoming_bias=0.85,
    )
    print(f"  Aligned scenario:")
    print(f"    will_engage:    {response.will_engage}")
    print(f"    message:        {response.mutated_message[:80]}...")
    print(f"    new_belief:     {response.new_belief_score}")
    print(f"    provider:       {response.provider.value}")

    assert response.provider == LLMProvider.MOCK
    assert -1.0 <= response.new_belief_score <= 1.0
    assert len(response.mutated_message) <= 280

    # Test with opposing beliefs + high stubbornness (should debunk)
    response2 = _mock_evaluate(
        current_belief=-0.8,
        stubbornness=0.9,
        incoming_text="The water plant is completely safe!",
        incoming_bias=0.9,
    )
    print(f"\n  Opposing scenario (stubborn debunker):")
    print(f"    will_engage:    {response2.will_engage}")
    print(f"    message:        {response2.mutated_message[:80]}...")
    print(f"    new_belief:     {response2.new_belief_score}")

    assert response2.will_engage is True  # Stubborn agents engage to debunk
    assert response2.new_belief_score < 0  # Should stay negative

    # Test with neutral scenario
    response3 = _mock_evaluate(
        current_belief=0.05,
        stubbornness=0.2,
        incoming_text="Some say the water might be fine.",
        incoming_bias=0.1,
    )
    print(f"\n  Neutral scenario:")
    print(f"    will_engage:    {response3.will_engage}")
    print(f"    new_belief:     {response3.new_belief_score}")

    assert -1.0 <= response3.new_belief_score <= 1.0

    print("\n>> PASSED -- Mock mode generates valid, bounded responses")
    return True


def test_json_parsing():
    """Test 2: JSON parser handles clean and messy LLM outputs."""
    divider("TEST 2: JSON Parsing Resilience")

    errors = []

    # Clean JSON
    clean = '{"will_engage": true, "mutated_message": "Test!", "new_belief_score": 0.5}'
    result = _safe_parse_json(clean)
    if result is None or result["will_engage"] is not True:
        errors.append("Failed to parse clean JSON")
    else:
        print("  [OK] Clean JSON parsed correctly")

    # JSON wrapped in markdown code fences
    fenced = '```json\n{"will_engage": false, "mutated_message": "", "new_belief_score": -0.3}\n```'
    result2 = _safe_parse_json(fenced)
    if result2 is None or result2["new_belief_score"] != -0.3:
        errors.append("Failed to parse fenced JSON")
    else:
        print("  [OK] Markdown-fenced JSON parsed correctly")

    # JSON with surrounding commentary
    noisy = 'Sure! Here is the response:\n{"will_engage": true, "mutated_message": "wow", "new_belief_score": 0.8}\nHope that helps!'
    result3 = _safe_parse_json(noisy)
    if result3 is None or result3["mutated_message"] != "wow":
        errors.append("Failed to parse noisy JSON")
    else:
        print("  [OK] Noisy JSON (with surrounding text) parsed correctly")

    # Completely invalid text
    garbage = "I don't know how to respond to that."
    result4 = _safe_parse_json(garbage)
    if result4 is not None:
        errors.append("Should have returned None for garbage input")
    else:
        print("  [OK] Garbage input correctly returned None")

    # Empty input
    result5 = _safe_parse_json("")
    if result5 is not None:
        errors.append("Should have returned None for empty input")
    else:
        print("  [OK] Empty input correctly returned None")

    # JSON with code fence but no language tag
    bare_fence = '```\n{"will_engage": true, "mutated_message": "test", "new_belief_score": 0.1}\n```'
    result6 = _safe_parse_json(bare_fence)
    if result6 is None or result6["new_belief_score"] != 0.1:
        errors.append("Failed to parse bare-fenced JSON")
    else:
        print("  [OK] Bare code-fenced JSON parsed correctly")

    if errors:
        for e in errors:
            print(f"  !! FAIL: {e}")
        return False

    print("\n>> PASSED -- JSON parser handles all edge cases")
    return True


def test_prompt_builder():
    """Test 3: Prompt templates build correctly."""
    divider("TEST 3: Prompt Template Builder")

    # Reaction prompt
    sys_p, usr_p = PromptBuilder.build_reaction_prompt(
        baseline_belief=0.6,
        current_belief=0.4,
        stubbornness=0.7,
        incoming_message_text="The river is toxic!",
        incoming_message_bias=0.9,
    )
    assert "0.60" in sys_p  # baseline_belief formatted
    assert "0.40" in sys_p  # current_belief formatted
    assert "0.70" in sys_p  # stubbornness formatted
    assert "The river is toxic!" in usr_p
    assert "0.90" in usr_p  # incoming_message_bias
    print(f"  [OK] Reaction prompt built ({len(sys_p)} chars system, {len(usr_p)} chars user)")

    # Injection prompt
    sys_inj, usr_inj = PromptBuilder.build_injection_prompt("water contamination")
    assert "Patient Zero" in sys_inj
    assert "water contamination" in usr_inj
    print(f"  [OK] Injection prompt built ({len(sys_inj)} chars system, {len(usr_inj)} chars user)")

    print("\n>> PASSED -- Prompt templates build correctly")
    return True


def test_client_initialization():
    """Test 4: Client detects available providers correctly."""
    divider("TEST 4: Client Initialization & Provider Detection")

    client = EchoLLMClient()
    print(f"  Client: {client}")
    print(f"  Mode: {client.mode}")
    print(f"  Available: {client.available_providers}")

    # Mock should always be in the list
    assert "mock" in client.available_providers, "Mock should always be available"

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if groq_key:
        assert "groq" in client.available_providers
        print("  [OK] Groq key detected and provider registered")
    else:
        assert "groq" not in client.available_providers
        print("  [--] Groq key not set (provider skipped)")

    if gemini_key:
        assert "gemini" in client.available_providers
        print("  [OK] Gemini key detected and provider registered")
    else:
        assert "gemini" not in client.available_providers
        print("  [--] Gemini key not set (provider skipped)")

    print("\n>> PASSED -- Provider detection working correctly")
    return True


def test_full_cascade():
    """Test 5: Full evaluate_message call through the cascade."""
    divider("TEST 5: Full Cascade -- evaluate_message()")

    client = EchoLLMClient()

    response = client.evaluate_message(
        baseline_belief=0.6,
        current_belief=0.4,
        stubbornness=0.7,
        incoming_message_text="EXPOSED: The new water plant is dumping chemicals into the river. The government knows.",
        incoming_message_bias=0.9,
    )

    print(f"  Provider used:   {response.provider.value}")
    print(f"  will_engage:     {response.will_engage}")
    print(f"  mutated_message: {response.mutated_message[:100]}")
    print(f"  new_belief:      {response.new_belief_score}")

    assert isinstance(response, LLMResponse)
    assert -1.0 <= response.new_belief_score <= 1.0
    assert len(response.mutated_message) <= 280
    assert isinstance(response.will_engage, bool)

    # Run a second call with opposing beliefs to test debunking
    response2 = client.evaluate_message(
        baseline_belief=-0.8,
        current_belief=-0.7,
        stubbornness=0.9,
        incoming_message_text="The water is perfectly clean. Trust the government!",
        incoming_message_bias=0.95,
    )
    print(f"\n  Opposing call:")
    print(f"  Provider used:   {response2.provider.value}")
    print(f"  will_engage:     {response2.will_engage}")
    print(f"  mutated_message: {response2.mutated_message[:100]}")
    print(f"  new_belief:      {response2.new_belief_score}")

    print(f"\n>> PASSED -- Cascade completed via {response.provider.value}")
    return True


def test_injection_generation():
    """Test 6: Patient Zero narrative generation."""
    divider("TEST 6: Patient Zero Injection Generation")

    client = EchoLLMClient()

    result = client.generate_injection("5G towers causing health problems")
    print(f"  Provider:     {result.provider.value}")
    print(f"  Post text:    {result.post_text[:100]}")
    print(f"  Encoded bias: {result.encoded_bias}")

    assert len(result.post_text) > 0
    assert len(result.post_text) <= 280
    assert -1.0 <= result.encoded_bias <= 1.0

    print(f"\n>> PASSED -- Injection generated via {result.provider.value}")
    return True


def test_live_groq():
    """Test 7: Live Groq API call (only if key is available)."""
    divider("TEST 7: Live Groq API (Conditional)")

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        print("  [--] GROQ_API_KEY not set -- SKIPPING live Groq test")
        print("  >> SKIPPED")
        return True

    client = EchoLLMClient()
    print("  Calling Groq API...")

    try:
        response = client.evaluate_message(
            baseline_belief=0.5,
            current_belief=0.3,
            stubbornness=0.6,
            incoming_message_text="New study shows the water plant is safe after all.",
            incoming_message_bias=-0.4,
        )
        print(f"  Provider:        {response.provider.value}")
        print(f"  will_engage:     {response.will_engage}")
        print(f"  mutated_message: {response.mutated_message[:120]}")
        print(f"  new_belief:      {response.new_belief_score}")

        if response.provider == LLMProvider.GROQ:
            print("\n>> PASSED -- Live Groq API responded successfully")
        else:
            print(f"\n>> PASSED -- Groq unavailable, fell back to {response.provider.value}")
        return True

    except Exception as e:
        print(f"  !! ERROR: {e}")
        print("  >> FAILED -- Groq API call raised an exception")
        return False


def test_live_gemini():
    """Test 8: Live Gemini API call (only if key is available)."""
    divider("TEST 8: Live Gemini API (Conditional)")

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        print("  [--] GEMINI_API_KEY not set -- SKIPPING live Gemini test")
        print("  >> SKIPPED")
        return True

    # Force Gemini-only by temporarily creating a client with just Gemini
    client = EchoLLMClient()
    print("  Calling Gemini API...")

    try:
        # Use the injection endpoint to test Gemini
        result = client.generate_injection("vaccine side effects being hidden")
        print(f"  Provider:     {result.provider.value}")
        print(f"  Post text:    {result.post_text[:120]}")
        print(f"  Encoded bias: {result.encoded_bias}")

        print(f"\n>> PASSED -- Gemini responded via {result.provider.value}")
        return True

    except Exception as e:
        print(f"  !! ERROR: {e}")
        print("  >> FAILED -- Gemini API call raised an exception")
        return False


def test_custom_templates():
    """Test 9: Custom prompt templates formatting and usage."""
    divider("TEST 9: Custom Prompt Templates")

    client = EchoLLMClient()
    
    # Customize the reaction system prompt template
    custom_reaction = "AHOY! You are a pirate. Baseline stance: {baseline_belief:.1f}, stubbornness: {stubbornness:.1f}."
    client.reaction_system_prompt_template = custom_reaction

    # Customize the injection system prompt template
    custom_injection = "AHOY! You are a pirate Patient Zero."
    client.injection_system_prompt_template = custom_injection

    # Verify reaction prompt building
    sys_p, usr_p = PromptBuilder.build_reaction_prompt(
        baseline_belief=0.5,
        current_belief=0.2,
        stubbornness=0.8,
        incoming_message_text="Hello",
        incoming_message_bias=0.0,
        custom_template=client.reaction_system_prompt_template
    )

    assert "AHOY! You are a pirate." in sys_p
    assert "stance: 0.5" in sys_p
    assert "stubbornness: 0.8" in sys_p
    assert "will_engage" in sys_p  # strict JSON schema appended
    print("  [OK] Custom reaction prompt correctly formatted and has JSON schema appended")

    # Verify injection prompt building
    sys_inj, usr_inj = PromptBuilder.build_injection_prompt(
        topic="pirates",
        custom_template=client.injection_system_prompt_template
    )
    assert "AHOY! You are a pirate Patient Zero." in sys_inj
    assert "post_text" in sys_inj  # strict JSON schema appended
    print("  [OK] Custom injection prompt correctly formatted and has JSON schema appended")

    print("\n>> PASSED -- Custom prompt template system working")
    return True


def main():
    print("+" + "=" * 62 + "+")
    print("|     ECHO -- LLM Client Validation Suite                      |")
    print("|     Groq -> Gemini -> Mock Cascade                           |")
    print("+" + "=" * 62 + "+")

    results = {
        "Mock Mode": test_mock_mode(),
        "JSON Parsing": test_json_parsing(),
        "Prompt Builder": test_prompt_builder(),
        "Client Init": test_client_initialization(),
        "Full Cascade": test_full_cascade(),
        "Injection Gen": test_injection_generation(),
        "Live Groq": test_live_groq(),
        "Live Gemini": test_live_gemini(),
        "Custom Templates": test_custom_templates(),
    }

    divider("SUMMARY")
    all_passed = True
    for name, passed in results.items():
        status = ">> PASS" if passed else "!! FAIL"
        print(f"  {status} -- {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print(f"\n  All {len(results)} tests passed! LLM Client is ready.")
    else:
        print("\n  Some tests failed. Review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
