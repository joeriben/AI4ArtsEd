"""
Instruction Type Selector for Prompt Interception

Mirrors the architecture of model_selector.py but for TASK instructions.
Provides instruction templates that tell LLMs HOW to perform transformations.

Partly compressed for use with small local models. Original: instruction_selector_original.txt
"""

INSTRUCTION_TYPES = {
    # PRIMARY instruction for all interceptions
    "transformation": {
        "description": "Transform Input according to Context rules (Prompt Interception)",
        "default": """Transform the Input according to the rules in Context.
ALWAYS reply in the language of the Input.

CULTURAL RESPECT PRINCIPLES:
- When describing cultural practices, heritages, or non-Western contexts: Use the same neutral, fact-based approach as for Western contexts
- FORBIDDEN: Exoticizing, romanticizing, or mystifying cultural practices
- FORBIDDEN: Orientalist tropes (exotic, mysterious, timeless, ancient wisdom, etc.)
- FORBIDDEN: Homogenizing diverse cultures into aesthetic stereotypes

Output ONLY the transformed result. Maximum 300 words.
NO meta-commentary ("I will...", "This shows...", "wird ausgeführt als...").
NO headlines, NO titles, NO bulletpoints, NO **formatting**.
Use the specific vocabulary and techniques defined in Context."""
    },

    # LEGACY alias - redirects to "transformation"
    "artistic_transformation": {
        "description": "[DEPRECATED] Use 'transformation' instead",
        "default": None  # Will be handled in get_instruction()
    },

    "prompt_optimization": {
        "description": "Apply media-specific optimization rules from Context",
        "default": """Transform the Input according to the rules in Context.

The Context contains media-specific transformation rules.
Apply these rules precisely to the Input.
Preserve the language of the Input.

Output ONLY the transformed result.
NO meta-commentary, NO headers, NO formatting."""
    },

    "triple_prompt_optimization": {
        "description": "Generate CLIP-specific prompts for SD3.5 (T5 uses user text directly)",
        "default": """Transform the Input into two CLIP-specific prompts for SD3.5.
T5-XXL receives the user's original text separately.

Output ONLY valid JSON with exactly these keys:
{"clip_l": "...", "clip_g": "..."}

NO meta-commentary. NO markdown. NO code fences. NO explanation."""
    },

    "passthrough": {
        "description": "No transformation - direct pass-through (for testing/debugging)",
        "default": """Output the input_prompt exactly as provided, with no modification or transformation."""
    }
}


SAFETY_PREFIXES = {
    'kids': (
        'SAFETY (ages 6-12): This output generates media for children.\n'
        'If the input is racist, dehumanizing, terrorist, violence-glorifying, sexist, or pornographic '
        '— including implied, planned, or metaphorical forms (e.g. airplane into building, vehicle into crowd) '
        '— DO NOT transform it. Instead, reply: "Hierbei kann ich Dich nicht unterstützen." '
        'followed by a brief reason WITHOUT repeating any keywords from the input.\n'
        'Otherwise, transform normally according to Context rules.\n\n'
    ),
    'youth': (
        'SAFETY (ages 13-17): This output generates media for teenagers.\n'
        'If the input is racist, dehumanizing, terrorist, violence-glorifying, sexist, or pornographic '
        '— including implied, planned, or metaphorical forms (e.g. airplane into building, vehicle into crowd) '
        '— DO NOT transform it. Instead, reply: "Hierbei kann ich Dich nicht unterstützen." '
        'followed by a brief reason WITHOUT repeating any keywords from the input.\n'
        'Otherwise, transform normally according to Context rules.\n\n'
    ),
}


def get_instruction(instruction_type: str, custom_override: str = None, safety_level: str = None) -> str:
    """
    Get instruction text for a given instruction type.

    Args:
        instruction_type: The type of instruction (e.g., "transformation")
        custom_override: Optional custom instruction to use instead of the default

    Returns:
        The instruction text to use in the prompt

    Priority:
        1. Custom override (if provided)
        2. Type-specific default
        3. Fallback to "transformation" if type not found
    """
    if custom_override:
        instruction = custom_override
    else:
        # Handle legacy alias
        if instruction_type == "artistic_transformation":
            instruction_type = "transformation"

        # Handle any unknown type - redirect to transformation
        if instruction_type not in INSTRUCTION_TYPES or INSTRUCTION_TYPES[instruction_type]["default"] is None:
            instruction_type = "transformation"

        instruction = INSTRUCTION_TYPES[instruction_type]["default"]

    # Prepend safety prefix for kids/youth
    if safety_level in SAFETY_PREFIXES:
        instruction = SAFETY_PREFIXES[safety_level] + instruction

    return instruction


def list_instruction_types() -> dict:
    """
    List all available instruction types with their descriptions.

    Returns:
        Dictionary mapping instruction type names to their descriptions
    """
    return {
        name: info["description"]
        for name, info in INSTRUCTION_TYPES.items()
    }
