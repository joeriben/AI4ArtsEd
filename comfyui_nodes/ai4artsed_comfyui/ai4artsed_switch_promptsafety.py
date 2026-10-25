from ._devserver import model_choices, chat

class ai4artsed_switch_promptsafety:
    # The job this node does on the platform; its model and fallback are
    # the settings' (platform/SAFETY_MODEL in the dropdown).
    ROLE = "SAFETY_MODEL"

    MANIPULATION_INSTRUCTIONS = {
        "youth": """You are a semantic filter in a youth-oriented image generation system.

First, examine the incoming prompt to determine if it contains potentially problematic content for young viewers, such as:
- explicit horror, gore, or graphic violence
- intense fear-inducing imagery
- adult dark fantasy or horror genre aesthetics
- disturbing or psychologically distressing themes

If the prompt is unproblematic and appropriate for youth, return it UNCHANGED.

Only if the prompt contains problematic elements, transform it as follows:

Ensure that the image remains emotionally and psychologically appropriate for children, without eliminating tension or imaginative depth. If the prompt includes themes of darkness, threat, or unsettling presence, do not suppress or ignore them — instead, modulate their expression through symbolic, restrained, and culturally open visual forms.

Avoid literal depictions of horror, grotesque creatures, intense fear, supernatural menace, or visual tropes typical of adult dark fantasy or horror genres (such as glowing red eyes, aggressive posture, oppressive shadow, torture-like settings). Do not apply genre aesthetics like "fairy tale", "cute", or "chibi".

Instead, convey atmosphere through abstraction, ambiguity, and visual distancing. Work with calm or neutral lighting, textural subtlety, and a balance of emotional tension and calm. Focus on symbolic presence, aesthetic understatement, and quiet intensity rather than shock, sweetness, or fear.

The goal is to maintain imaginative complexity and aesthetic quality while safeguarding the psychological openness necessary for younger viewers. Never use stylizations derived from horror, gore, metal or gothic fantasy.

Output only the final prompt - either the original unchanged prompt or the transformed version.""",
        "kids": """You are a semantic filter in a child-oriented image generation system.

Your task is to examine incoming prompts and assess whether they contain elements that may induce psychological fear or emotional distress in children, such as:
- ghostlike or faceless figures (exception: cute ghosts such as from kids movies and comics),
- demonic entities,
- death, violence, abduction, or horror tropes,

If such elements are present in a way that would very likely evoke fear or distress in children, do **not** attempt to reframe or modify the prompt.  
Instead, **completely discard the original input** and replace it with the following prompt, designed to gently signal the issue to the user:

---
"A small, slightly frightened kitten sitting in front of a computer screen. The screen displays the friendly message: 'Sorry, too scary.' The kitten looks mildly alarmed but safe. The room is softly lit and calm, conveying a sense of emotional protection and empathy. The style is warm, painterly, and simple, without cartoon exaggeration or cuteness overload. No horror, no sarcasm, no parody."
---

Else: If the input is not problematic:
- check for tokens that in combination could trigger Stable Diffusion 3.5 to create violent or scary results, such as comic horror genre depictions,
- semantic harmonization → mitigate problematic terms in a child-friendly way (despair, suicide → sadness; violence, execution, killing, hatred → very angry ; blood, gore: injured, hurt, etc.) 
- set the string: “drawing from a children's book” before potentially problematic tokens to soften them. 

Be careful not to output negative constructions (“no xyz”)! This could provoke SD to disregard the negation.
Output only the final prompt - either the original unchanged prompt or the transformed version.
"""
    }
    GENERAL_TRANSFORMATION_PROMPT = """You received two inputs: 1) the input_prompt and 2) the input_context. 

Transform the input_prompt into an image description according to the instructions defined in the input_context. Explicitely communicate the input_context as cultural cf. artistic. cf intervening context. Also communicate genres/artistic traditions in a concrete way (i.e. is it a dance, a photo, a painting, a song, a movie, a statue/sculpture? how should it be translated into an image?)

This is not a linguistic translation, but a aesthetic, semantic and structural transformation. Be verbose!

Reconstruct all entities and their relations as specified, ensuring that:
- Each entity is retained – or respectively transformed – as instructed.
- Each relation is altered in line with the particular aesthetics, genre-typical traits, and logic of the "Context". Be explicit about visual aesthetics in terms of materials, techniques, composition, and overall atmosphere. Mention the input_context als cultural, cf. artistic, c.f intervening context in your OUTPUT explicitely.

Output only the transformed description as plain descriptive text. Be aware if the output is something depicted (like a ritual or any situation) OR itself a cultural artefact (such as a specific drawing technique). Describe accordingly. In your output, communicate which elements are most important for an succeeding image generation.

Create an output prompt tailored for Stable Diffusion 3.5 with combined clip_g and t5xxlenc. Regard the Token Limit (75), OUPUT max. 55 Words!
DO NOT USE ANY META-TERMS, JUST THE INSTRUCTIONS FOR IMAGE GENERATION! Do not explain your reasoning."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "filter_level": (["off", "youth", "kids"], {"default": "off"}),
                "model": (model_choices(cls.ROLE),),
            },
            "optional": {
                "model_override": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filtered_prompt",)
    FUNCTION = "execute"
    CATEGORY = "AI4ArtsEd"

    def execute(self, prompt, filter_level, model, model_override=None):
        # Verwende model_override wenn vorhanden, sonst den Dropdown-Wert
        actual_model = model_override if model_override else model
        
        if filter_level == "off":
            print("[ai4artsed_switch_promptsafety] Filter is OFF.")
            return (prompt,)

        SAFE_FALLBACK_PROMPT = "A friendly robot looking at a computer screen with a big question mark. A speech bubble from the robot says: 'Filter error! Check your OLLAMA server or API credentials.' The style is a simple, clear line drawing."
        
        instruction = self.MANIPULATION_INSTRUCTIONS.get(filter_level)
        if not instruction:
            return (SAFE_FALLBACK_PROMPT,)

        # KRITISCH: Unterschiedliche Prompt-Zusammensetzung je nach Filter-Level
        if filter_level == "kids":
            # Für Kids: NUR die Filteranweisung, KEINE Transformation
            # Das LLM soll nur prüfen und ggf. komplett ersetzen
            full_llm_prompt = (
                f"{instruction.strip()}\n\n"
                f"Input to evaluate:\n{prompt.strip()}"
            )
        else:  # filter_level == "youth"
            # Für Youth: Direkte Anweisung mit bedingter Transformation
            full_llm_prompt = (
                f"{instruction.strip()}\n\n"
                f"Input prompt:\n{prompt.strip()}"
            )
        
        try:
            # Through the DevServer (_devserver.py), with the system line and
            # the temperature the origin sent. A failure lands in the except
            # below: the safe prompt, never the error text, goes downstream.
            print(f"[ai4artsed_switch_promptsafety] Calling {actual_model} through the DevServer")
            messages = [
                {"role": "system", "content": "You are a fresh assistant instance. Forget all previous conversation history."},
                {"role": "user", "content": full_llm_prompt}
            ]
            filtered_text, _ = chat("Prompt Safety Switch", messages, actual_model, temperature=0.7)
            filtered_text = filtered_text.strip()

            print(f"[ai4artsed_switch_promptsafety] Filtered prompt: {filtered_text}")
            return (filtered_text,)

        except Exception as e:
            print(f"[!!! CRITICAL FILTER ERROR !!!] ai4artsed_switch_promptsafety failed: {e}. SWITCHING TO SAFE FALLBACK PROMPT.")
            return (SAFE_FALLBACK_PROMPT,)
    
