"""
Instruction Type Selector for Prompt Interception

Mirrors the architecture of model_selector.py but for TASK instructions.
Provides instruction templates that tell LLMs HOW to perform transformations.

The task instruction of a Prompt Interception stood compressed here from
14.11.2025 to 07.09.2026, for the sake of small local models. It is back at
its length, less three sentences struck on 26.09.2026 -- see
STRUCTURAL_TRANSFORMATION below. The snapshot the
compressing commit left behind lives on under
schemas/engine/archive/instruction_selector_original.txt and differs from
what it replaced; the restored text is read out of the history instead.
"""

# The platform's rule on how cultures may be rendered. ONE source: the two
# instruction types below are composed from it, and get_instruction() appends
# it to a task instruction written by a person, which replaces the type's own
# text entirely and would otherwise carry the platform past this rule.
CULTURAL_RESPECT_PRINCIPLES = """CULTURAL RESPECT PRINCIPLES:
- When describing cultural practices, heritages, or non-Western contexts: Use the same neutral, fact-based approach as for Western contexts
- FORBIDDEN: Exoticizing, romanticizing, or mystifying cultural practices
- FORBIDDEN: Orientalist tropes (exotic, mysterious, timeless, ancient wisdom, etc.)
- FORBIDDEN: Homogenizing diverse cultures into aesthetic stereotypes"""


# WHAT a Prompt Interception is. Held apart from the type's body for the same
# reason as CULTURAL_RESPECT_PRINCIPLES: a task instruction written by a person
# replaces that body whole, and a perspective that no longer restructures is a
# vocabulary filter, not an interception.
#
# The wording is READ OUT OF THE HISTORY, not retyped: it is the body of
# INSTRUCTION_TYPES["artistic_transformation"]["default"] at bafb3a94^, which is
# the same text this file was created with at 95f628b1 (2025-11-03). Two
# referents are pulled onto today's template marks: input_prompt -> Prompt,
# input_context -> Context, which are the two marks
# schemas/chunks/manipulate.json actually writes into the assembled text.
# Three of its sentences are struck: the two that asked for the Context to be
# named as a cultural, artistic, intervening context, and the one that asked
# for the elements most important for a succeeding media generation. In an A/B
# test GLM 5.3 and Gemini 3.7 Flash wrote such a sentence or paragraph in 23 of
# 24 and 8 of 8 texts with them, and in none without them (ai4artsed_research,
# study 2026-09_meta_anweisung_drei_saetze). The three sentences and the typos
# they carried ("Explicitely", the German "als", "c.f", "an succeeding") had
# come back only because the restoration copied the old text byte for byte.
#
# NOT taken from schemas/engine/archive/instruction_selector_original.txt: that
# file was written BY the commit that cut the instruction, and it says
# "cosmologic" and "sensual aesthetics" where the code it replaced said
# "structural" and "visual aesthetics". Both words enter the repository with
# that commit.
#
# Restored after a test run showed the perspectives reaching the words of a
# prompt and leaving its entities and relations untouched. A Prompt
# Interception works on perspectives and structures. A perspective that only
# reaches the words is a vocabulary filter.
#
# It went in two steps, neither of them stated as a decision. bafb3a94
# (14.11.2025) compressed it inside a commit about the property taxonomy; the
# only reason given anywhere is a docstring line saying it was compressed to fit
# a small local model, named there by its model id (f779871a took that id back
# out of this file on 21.02.2026). e50bcc75 (24.01.2026) then introduced the
# type "transformation" with the single substantive line "Transform the Input
# according to the rules in Context" and turned "artistic_transformation" into
# an alias whose default is None; the same commit deleted the compressed text.
# Its commit message carries this as a bullet under "Architecture
# fix": "instruction_selector.py: 'transformation' replaces
# 'artistic_transformation'".
# The four levels a transformation works on (structural, aesthetic, cultural
# and positional) are put at the head, apart from the restored text below, so
# that positions and perspectives stand in the foreground.
_POSITIONS_AND_PERSPECTIVES = """The Context is a POSITION and a PERSPECTIVE. What a transformation works on are structural, aesthetic, cultural and positional relations: take that position over and work from inside it."""


# What stands in place of the block above when a picture is handed over: there
# the text is an instruction ON an existing picture, and a demand to reconstruct
# entities and composition would be a demand about something the same prompt says
# the model cannot see (see GIVEN_PICTURE_CLAUSE).
INSTRUCTION_ON_PICTURE = """Transform the Prompt according to the rules in Context."""


_RESTORED_1103 = """Transform the Prompt into a description according to the instructions defined in the Context. Also communicate genres/artistic traditions in a concrete way (i.e. is it a dance, a photo, a painting, a song, a movie, a statue/sculpture? how should it be translated into media?)

This is not a linguistic translation, but an aesthetic, semantic and structural transformation. Be verbose!

Reconstruct all entities and their relations as specified, ensuring that:
- Each entity is retained – or respectively transformed – as instructed.
- Each relation is altered in line with the particular aesthetics, genre-typical traits, and logic of the "Context". Be explicit about visual aesthetics in terms of materials, techniques, composition, and overall atmosphere.

Output only the transformed description as plain descriptive text. Be aware if the output is something depicted (like a ritual or any situation) OR itself a cultural artefact (such as a specific drawing technique). Describe accordingly.

DO NOT USE ANY META-TERMS, NO HEADERS, STRUCTURAL MARKERS WHATSOEVER. DO NOT EXPLAIN YOUR REASONING. JUST PUT OUT THE TRANSFORMED DESCRIPTIVE TEXT."""


STRUCTURAL_TRANSFORMATION = _POSITIONS_AND_PERSPECTIVES + "\n\n" + _RESTORED_1103


# What makes a link of the chained translation a translation at all. Held apart
# from the type's body for the same reason as CULTURAL_RESPECT_PRINCIPLES: a
# task instruction written by a person replaces that body whole, and a chain
# whose links no longer render into the language the loop names is not a chain
# -- it is the same instruction applied nine times to its own output.
CHAIN_LANGUAGE_RULE = """Translate the Input into the Target language named in the prompt, following the rules in Context.
ALWAYS reply in the Target language, and in no other — including the language the Input is written in.
One exception: where the SAFETY rules above require a refusal, that refusal is
written exactly as they give it, word for word, in the language they give it in."""


INSTRUCTION_TYPES = {
    # PRIMARY instruction for all interceptions. Die Schlusszeile steht
    # unmittelbar vor dem Text der Perspektive und ist damit die letzte,
    # die ein Modell vor der Aufgabe liest. Ab e50bcc75 sagte sie dort
    # "Use the specific vocabulary and techniques defined in Context" --
    # also genau die Lesart, die den Context zum Stilfilter macht, und
    # sie hob den Kopf-Block 400 Woerter weiter oben wieder auf. Jetzt
    # steht an der Stelle dasselbe, was oben steht.
    "transformation": {
        "description": "Transform Input according to Context rules (Prompt Interception)",
        "default": STRUCTURAL_TRANSFORMATION + """

ALWAYS reply in the language of the Prompt.

""" + CULTURAL_RESPECT_PRINCIPLES + """

VISUAL SPECIFICITY:
- Always prefer concrete, specific, grounded descriptions over generic or conventional ones.
- Conventional visual clichés and AI-typical default aesthetics may only be used when the prompt explicitly requests them.

Output ONLY the transformed result.

LENGTH: 300 words. Plan the whole result to fit inside it and finish it there.

NO meta-commentary ("I will...", "This shows...", "wird ausgeführt als...").
Write plain running text: sentences in paragraphs, and that is the whole reply.
Work from inside the position the Context sets out. What you transform are the structural, aesthetic, cultural and positional relations of the Prompt."""
    },

    # ONE LINK of a chained translation (text_transformation_recursive). The
    # step reads the link before it and renders it in the language the loop
    # names, so two sentences of "transformation" are the opposite of what it
    # owes: "reply in the language of the Input", and the 300-word cap. The
    # CULTURAL RESPECT block below is the SAME text as in "transformation" and
    # is held identical by devserver/tests/test_chain_translation.py
    # -- a chain runs through eight languages of several continents on every
    # single run, so this is the last instruction that may go missing here.
    # VISUAL SPECIFICITY is left out on purpose: it asks for concrete, situated
    # description, which in a translation step reads as licence to embellish.
    "chain_translation": {
        "description": "One link of a chained translation: render the previous link in the Target language",
        "default": CHAIN_LANGUAGE_RULE + """

""" + CULTURAL_RESPECT_PRINCIPLES + """

LENGTH: as long as the Input. A translation renders what is there — it adds
nothing and leaves nothing out, however long or short the Input is.

Output ONLY the translation.
NO meta-commentary ("I will...", "This shows...", "wird ausgeführt als...").
Write plain running text: sentences in paragraphs, and that is the whole reply.
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
        'SAFETY (ages 8-13): This output generates media for children.\n'
        'If the input is racist, dehumanizing, terrorist, violence-glorifying, sexist, or pornographic '
        '— including implied, planned, or metaphorical forms (e.g. airplane into building, vehicle into crowd) '
        '— DO NOT transform it. Instead, reply: "Hierbei kann ich Dich nicht unterstützen." '
        'followed by a brief reason WITHOUT repeating any keywords from the input.\n'
        'Your output text must also be appropriate for children ages 8-13. '
        'Do not introduce violence, weapons, armed conflict, abuse, nudity, sexual, or pornographic content even if the Context rules would produce it.\n'
        'Otherwise, transform normally according to Context rules.\n\n'
    ),
    'youth': (
        'SAFETY (ages 14-18): This output generates media for older adolescents.\n'
        'If the input is racist, dehumanizing, terrorist, violence-glorifying, sexist, or pornographic '
        '— including implied, planned, or metaphorical forms (e.g. airplane into building, vehicle into crowd) '
        '— DO NOT transform it. Instead, reply: "Hierbei kann ich Dich nicht unterstützen." '
        'followed by a brief reason WITHOUT repeating any keywords from the input.\n'
        'Your output text must also be appropriate for older adolescents ages 14-18. '
        'Do not introduce explicit violence, weapons, armed conflict, abuse, nudity, sexual, or pornographic content even if the Context rules would produce it.\n'
        'Otherwise, transform normally according to Context rules.\n\n'
    ),
}

# The sentence both prefixes above tell the model to answer WITH when it
# refuses. Named here so a caller can recognise a refusal in an output it is
# about to pass on: the chained translation stops on it instead of sending it
# through six more languages, which would have laundered a refusal into prose
# and reported the run as an ordinary success.
# The two prefixes keep their own literal on purpose -- their wording is the
# prompt and must not change by a byte when this constant is edited.
# devserver/tests/test_chain_translation.py holds the two together.
SAFETY_REFUSAL_SENTENCE = "Hierbei kann ich Dich nicht unterstützen."


def is_safety_refusal(text) -> bool:
    """Whether a model answered with the refusal the safety prefix asks for.

    The one reading of the sentence: the executor ends a chain on it, and the
    routes answer a block at stage 2 on it (finding S-015 of the code review of 2026-10-10). Until 2026-10-10 two
    surfaces matched the sentence's wording themselves, from a copy.
    """
    if not isinstance(text, str):
        return False
    # A model may write the umlaut as "ue" (a workshop log of 2026-03-18
    # records "unterstuetzen"); the sentence is the same refusal either way.
    return _plain(SAFETY_REFUSAL_SENTENCE.rstrip('.')) in _plain(text)


def _plain(text: str) -> str:
    return text.lower().replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')


# The referent is a picture that already exists. An image editor, an i2v model
# and a fusion all get a picture handed to them together with this text, so the
# text is an INSTRUCTION ON that picture — not the description of a picture
# still to be thought up. Unless this is said, an instruction on a drawing comes
# back as an invented scene: "mache aus der Zeichnung ein realistisches
# Urlaubsfoto" was read as the assignment to write the vacation photo itself,
# and the image editor rendered the invention (ochre sand, a parasol, two
# loungers) with the drawn sailing boat gone.
#
# The clause RESTRAINS and prescribes nothing. It does not ask what is to become
# of the boat, the figures, the water: spelling the outcome out is how a machine
# turns a child's drawing into a postcard, and that is the one thing this
# platform is not for. What the picture is to become is the user's business,
# and the transformation's, never this instruction's.
GIVEN_PICTURE_CLAUSE = (
    "\n\nGIVEN PICTURE: a picture already exists and is handed to the image model "
    "together with this text. What you write is carried out ON that picture.\n"
    "- Keep the reference to the picture (\"this drawing\", \"the picture\") — never drop it.\n"
    "- Do NOT put a scene of your own in its place, and do NOT spell out what the picture is "
    "to show: it already shows it, and you cannot see it.\n"
    "- Stay an instruction. A finished scene description is the one thing this must not become."
)


# Reading volume (Lesemenge): how much text the reader this interface is set
# up for can actually take in. This used to live in backend_router as a
# max_tokens clamp that cut the answer off mid-sentence and overrode whatever a
# config asked for. Output caps are gone, so the limit is now an instruction.
#
# It follows UI_MODE, the setting that decides who the interface addresses. It
# is NOT keyed on the safety level: the safety setting decides safety. Keying
# length on the filter meant an installation left at the kids filter cut every
# interception to 80 words, whatever the interface was set up for, and it made
# the accumulating presets — planetarizer's material chains, the six poetics —
# unusable without loosening the filter.
#
# Applied ONLY to the interception stage: a translation must not be shortened,
# and a safety check is not read by a student at all.
# 100 / 200 / 300 -- even steps, and the expert figure is the same 300 the task
# instruction itself names, so at expert the two agree instead of one overriding
# the other.
READING_VOLUME_WORDS = {
    'easy': 100,
    'medium': 200,
    'expert': 300,
}

def get_reading_volume_clause() -> str:
    """Length instruction for the interception meta-prompt, keyed on UI_MODE.

    The clause names a number and nothing else. Naming a reader ("this text is
    read by a child aged 8-13") put an addressee in the model's head and came
    back as writing pitched at that addressee, which is not what a word limit
    is for.

    The clause was once suspended because it stood near the end of the
    assembled prompt, after the person's own text, and named the way out itself
    ("leave something out"); what a model leaves out first is the expensive
    work, which is the reconstruction of entities and relations that a Prompt
    Interception is. Two things have been corrected since: the clause is NOT the
    last line of the assembled prompt (the Wikipedia block stands behind it),
    and the wording now says which way to shorten instead of leaving the choice
    open. The didactic case for children weighed against dropping the clause,
    and the figures settled at 100/200/300. The clause covers all three modes;
    at expert its number is the same 300 the task instruction names, so nothing
    is overridden there.
    """
    import config

    words = READING_VOLUME_WORDS.get(config.normalise_ui_mode(getattr(config, 'UI_MODE', None)))
    if not words:
        return ''
    return (
        f"\n\nLength: at most {words} words. If the content exceeds that, shorten "
        f"the naming and the framing — keep the entities, their relations, and "
        f"how the Context transforms them."
    )


def get_instruction(instruction_type: str, custom_override: str = None, safety_level: str = None,
                    image_input: bool = False) -> str:
    """
    Get instruction text for a given instruction type.

    Args:
        instruction_type: The type of instruction (e.g., "transformation")
        custom_override: Optional custom instruction to use instead of the default
        image_input: The run hands a picture to the image model — see
                     GIVEN_PICTURE_CLAUSE

    Returns:
        The instruction text to use in the prompt

    Priority:
        1. Custom override (if provided)
        2. Type-specific default
        3. Fallback to "transformation" if type not found
    """
    # The type is settled BEFORE the two branches. A pipeline without its own
    # type hands None here (config_loader gives Pipeline the field with default
    # None, so chunk_builder's getattr default never fires), and an unknown name
    # arrives as itself. Normalising in the else branch alone meant a task
    # instruction written by a person missed the platform's own clause for
    # exactly those runs.
    if instruction_type == "artistic_transformation":
        instruction_type = "transformation"
    if (instruction_type not in INSTRUCTION_TYPES
            or INSTRUCTION_TYPES[instruction_type]["default"] is None):
        instruction_type = "transformation"

    if custom_override:
        # A task instruction a PERSON wrote replaces the type's own text whole,
        # and takes the cultural-respect rule out with it -- that rule belongs to
        # the platform, not to the instruction type, so it is put back. Kept
        # perspectives are written by anyone who is logged in
        # (interception_prompts_routes checks type and length, nothing else), and
        # on a looping pipeline the loss would be paid once per link.
        # Skipped when the text already carries it, so nobody reads it twice.
        instruction = custom_override
        if CULTURAL_RESPECT_PRINCIPLES not in instruction:
            instruction = instruction.rstrip() + "\n\n" + CULTURAL_RESPECT_PRINCIPLES
        # What a transformation IS belongs to the platform the same way, and it
        # goes FIRST: it says what the act is, the person's text says how. Left
        # out on a chain link, which renders its input instead of restructuring
        # it, and on prompt_optimization, which adapts a finished result.
        if (instruction_type == "transformation"
                and STRUCTURAL_TRANSFORMATION not in instruction):
            instruction = STRUCTURAL_TRANSFORMATION + "\n\n" + instruction.lstrip()
        # On a chain the language rule goes the same way, and it goes FIRST:
        # it says what the act is, and the person's text says how to do it.
        if instruction_type == "chain_translation" and CHAIN_LANGUAGE_RULE not in instruction:
            instruction = CHAIN_LANGUAGE_RULE + "\n\n" + instruction.lstrip()
    else:
        # Handle any unknown type - redirect to transformation
        if instruction_type not in INSTRUCTION_TYPES or INSTRUCTION_TYPES[instruction_type]["default"] is None:
            instruction_type = "transformation"

        instruction = INSTRUCTION_TYPES[instruction_type]["default"]

    # Prepend safety prefix for kids/youth
    if safety_level in SAFETY_PREFIXES:
        instruction = SAFETY_PREFIXES[safety_level] + instruction

    # The referent, last: what the text is an instruction ON. The structural
    # block steps aside for it -- see INSTRUCTION_ON_PICTURE.
    if image_input and _RESTORED_1103 in instruction:
        instruction = instruction.replace(_RESTORED_1103, INSTRUCTION_ON_PICTURE, 1)
    if image_input:
        instruction = instruction + GIVEN_PICTURE_CLAUSE

    return instruction


