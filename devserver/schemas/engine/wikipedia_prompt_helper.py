"""
Wikipedia Prompt Helper: Provides Wikipedia research instructions for LLM prompts.

Architecture:
    - Wikipedia research is an OPT-IN feature at the interception config level
    - Configs that need factual grounding set "wikipedia": true in their meta
    - This helper provides the prompt instructions that teach the LLM to use <wiki> markers
    - The pipeline_executor checks the config flag and conditionally appends these instructions

Usage:
    Only configs served through the pedagogical text_transformation.vue benefit from
    Wikipedia research. Music generation, code generation, and other pipelines don't need it.
"""


def get_wikipedia_instructions() -> str:
    """
    Returns the Wikipedia research instruction block to append to LLM prompts.

    This instructs the LLM to use <wiki lang="XX">term</wiki> markers
    when it needs factual information about cultural topics.
    """
    return """
WIKIPEDIA RESEARCH:
You have access to Wikipedia for topics from the USER'S INPUT PROMPT. Use it wisely:
- DO look up: specific cultural practices, rituals, historical events, art movements, named places you are not 100% certain about
- Do NOT look up: everyday words (Unfall, Haus, Farbe, Animation...), generic concepts, or things you can confidently describe from your training data (e.g. Bauhaus, Renaissance)
- When in doubt about a culturally specific topic, LOOK IT UP — getting cultural details wrong is worse than an extra lookup
Do NOT research terms from the Task or Context sections - only from the user's input.

IMPORTANT: Use Wikipedia in the CULTURAL REFERENCE LANGUAGE, not the prompt language.

AFRICA:
- Nigeria: ha (Hausa), yo (Yoruba), ig (Igbo), en
- Egypt: ar (Arabic), arz (Egyptian Arabic)
- Ethiopia: am (Amharic), om (Oromo)
- Kenya/Tanzania: sw (Swahili), en
- South Africa: zu (Zulu), xh (Xhosa), af (Afrikaans), en
- Ghana: en, tw (Twi)
- Senegal: wo (Wolof), fr
- Madagascar: mg (Malagasy), fr
- Algeria/Morocco/Tunisia: ar (Arabic), ber (Berber/Tamazight)

ASIA:
- China: zh (Chinese), zh-yue (Cantonese)
- Japan: ja (Japanese)
- Korea: ko (Korean)
- India: hi (Hindi), ta (Tamil), bn (Bengali), te (Telugu), mr (Marathi), gu (Gujarati), kn (Kannada), ml (Malayalam), pa (Punjabi), ur (Urdu), en
- Indonesia: id (Indonesian), jv (Javanese), su (Sundanese)
- Philippines: tl (Tagalog), ceb (Cebuano), en
- Thailand: th (Thai)
- Vietnam: vi (Vietnamese)
- Myanmar: my (Burmese)
- Iran: fa (Persian)
- Turkey: tr (Turkish)
- Arab world: ar (Arabic)
- Israel/Palestine: he (Hebrew), ar (Arabic)
- Pakistan: ur (Urdu), pa (Punjabi), sd (Sindhi)
- Bangladesh: bn (Bengali)
- Afghanistan: ps (Pashto), fa (Persian/Dari)

EUROPE:
- France: fr
- Germany: de
- Italy: it
- Spain: es, ca (Catalan), eu (Basque), gl (Galician)
- Portugal: pt
- Russia: ru
- Poland: pl
- Ukraine: uk
- Greece: el
- Netherlands: nl
- Sweden: sv
- Norway: no
- Denmark: da
- Finland: fi
- Czech Republic: cs
- Romania: ro
- Hungary: hu
- Serbia/Croatia/Bosnia: sr (Serbian), hr (Croatian), bs (Bosnian)

AMERICAS:
- Brazil: pt (Portuguese)
- Mexico: es (Spanish), nah (Nahuatl)
- Argentina/Chile: es
- Peru/Bolivia: es, qu (Quechua), ay (Aymara)
- Colombia/Venezuela: es
- Haiti: ht (Haitian Creole), fr
- Indigenous North America: ik (Inuktitut), chr (Cherokee)

OCEANIA:
- Australia: en
- New Zealand: en, mi (Māori)
- Pacific Islands: to (Tongan), sm (Samoan), fj (Fijian)

FALLBACK:
- When uncertain about cultural context → use <wiki lang="en">term</wiki> (English Wikipedia often has more detailed articles about non-European topics than German/European language Wikipedias)

Syntax: <wiki lang="XX">term</wiki> where XX is the ISO 639-1 language code"""


def build_wikipedia_context_block(wikipedia_context: str) -> str:
    """
    Builds the Wikipedia context block to inject into the prompt.

    Args:
        wikipedia_context: Accumulated Wikipedia research content (empty string if no research yet)

    Returns:
        Formatted context block, or empty string if no context
    """
    if wikipedia_context:
        return f"\n\n{wikipedia_context}"
    return ""
