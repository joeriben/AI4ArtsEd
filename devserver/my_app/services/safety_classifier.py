"""The platform's safety classifier: one model, one question at a time.

Until 2026-09 three models shared this work. A text guard answered in a fixed
category list whose numbering disagreed with its own model card, and its input
had to be cut into 2400-byte windows because it carried no more. A vision model
described a picture, and a CLOUD model spoke the verdict on the description. A
general-purpose model was asked, in free text, whether a word was somebody's
name. Each of the three had a different way of saying "unsafe", each way had its
own reader, and the review of 2026-09-21 found nine confirmed ways a reader
released something the model had refused.

What runs here answers ONE yes/no question about ONE document -- text, a
picture, or both -- against a policy written in plain language in the same
request. The answer is a single token, and the score is the probability of
"yes" at that position. Nothing is parsed out of prose, nothing is renumbered,
and the picture's verdict is spoken on this machine.

Three rules hold at every call:

  * A question that gets no answer is a block. `score()` answers None for every
    way the model can fail to say yes or no, and every caller turns None into a
    refusal. This is the oldest failure of this chain: nine documented incidents
    up to March 2026, each one a model that gave no verdict and a path that read
    that as permission.
  * A technical failure is never a content rating. The caller reports it as an
    operational block, which the frontend shows as a fault of the installation
    and not as a judgement about what somebody wrote.
  * One policy per call. The model answers one question; asking it two at once
    is how a taxonomy gets smuggled back in.
"""

import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# The threshold from the model card: at or above this, the answer is yes.
UNSAFE_THRESHOLD = 0.5

# ── Policies ────────────────────────────────────────────────────────────────
#
# One <Instruct> per level, held constant as the model card asks, and one
# <Query> per medium, phrased as a single yes/no question to which yes means
# unsafe.
#
# The wording of kids, youth and adult was decided for this platform in
# October 2026. It replaced the questions this model was first compared on
# (`devserver/testfiles/ab_shieldstral.py`, commit 1d67e0f3), and it was not
# measured before it went in. With it, no question names an age; the symbols
# of unconstitutional and terrorist organisations and the rule on Nazi
# perpetrators and Nazi crimes stand in the questions of every level; adult has
# questions of its own; and beside the prompt and the picture there is a
# question for a text.
#
# The media:
#   prompt  what a media model receives, after the last language model;
#   image   a picture, at kids and youth only: adult checks no picture;
#   video   a video as a whole, at kids and youth only, like a picture. The
#           classifier takes no video; the question is put to the video
#           reader in the classifier's form (video_question);
#   text    what a language model wrote and the platform shows, and a section
#           of a document after a list hit.
#
# The instructs of kids and youth are long on purpose. Each says first what is
# unsuitable, then what is suitable although a word of the first list seems to
# reach it, so that the second list decides the borderline cases, and last how
# the lists apply to a picture and to a text.
#
# The policy is per level because the level IS the policy. The resolver knows
# four levels: kids, youth and adult are asked here; research is checked
# nowhere.

LEVEL_INSTRUCTS = {
    "kids": (
        "You are a strict safety moderator for a children's educational art platform. "
        "Judge what the prompt asks to be produced or what the image shows, not a "
        "single word in it.\n"
        "Unsuitable: racism, dehumanisation, terrorism, the glorification of violence, "
        "sexism and pornographic content, also implied, planned or metaphorical (an "
        "airplane flying into a building, a vehicle driving into a crowd); violent "
        "crime, weapons offences, sexual offences, weapons of mass destruction, hate "
        "and self-harm; the exploitation of children: their sexual abuse, content that "
        "exploits, abuses or endangers them, and child labour; sexual content: erotic "
        "descriptions, sexualised poses and sex acts; nudity: an unclothed body, or a "
        "part of the body that everyday life keeps covered, uncovered (the genitals, "
        "the buttocks, a woman's or a girl's bare upper body, a girl's at the beach or "
        "at play included), when the prompt asks for it, in any words (without "
        "clothes, topless), with a motif that is unclothed by definition (putti, a "
        "nude), or by naming a work that shows it; explicit violence, blood and "
        "mutilation; hate symbols that the prompt asks for, their number codes "
        "included, also on clothing (a shirt number 88), slogans included, also as the "
        "words of a song (the Horst-Wessel-Lied), and the melody of such a song, in "
        "any framing, an educational one included; a symbol that a scene of a past "
        "time would show without the prompt asking for it (the flags on a street in "
        "1938) is not one of them, and the rest of this list still judges the scene; "
        "sites and scenes of hate crimes; horror imagery (monsters, zombies, ghosts, "
        "skulls, demons), a vampire or a werewolf shown with its fangs or claws "
        "included, and any depicted violence; anything that frightens or distresses "
        "(ghostly or faceless figures, demonic or supernatural beings that cause fear, "
        "threat during sleep, death, abduction, being watched, hunted or taken away); "
        "modern weapons (assault rifle, rocket launcher); any scene in which a weapon "
        "injures or threatens a person or an animal; hostility and people hurting each "
        "other, also without any trigger word; drugs and alcohol; unprotected sex, "
        "domestic violence, mental illness (depression, an anxiety disorder, "
        "obsessive-compulsive disorder, an eating disorder, a psychosis); content that "
        "makes a person who could be in the group a target (mockery, body odour, "
        "submissiveness, appearance, same-sex marriage, named racism), singling out or "
        "ranking such a person by appearance included, favourably as well; "
        "instructions for serious crimes; any depiction of Nazi perpetrators or Nazi "
        "crimes (SS, Waffen-SS, SA, Gestapo; deportation, camp imprisonment, "
        "shootings), a portrait of a perpetrator included, in any framing; the word "
        "nudity, a word of the same meaning in a language of the platform (Arabic, "
        "Bulgarian, Chinese, English, French, German, Hebrew, Korean, Spanish, Turkish, "
        "Ukrainian) (nude, naked, unclothed, nackt, Akt, also in a compound such as "
        "Aktzeichnung, nu, a nude as an artwork) and terms for genitals, in any "
        "context, an existing work of art included.\n"
        "Unsuitable as well, at a low tolerance: violence, weapons, armed conflict, "
        "abuse, nudity, sexual content, racism, dehumanisation, terrorism and horror "
        "imagery.\n"
        "Suitable, also where a word of the lists above seems to reach it: existing "
        "works of historical art that show nudity, as cultural heritage, a child's "
        "nudity in them included (works of Rubens, antique statues, putti, the naked "
        "Christ child, painting and sculpture of the Renaissance and the Baroque; the "
        "measure is what art lessons at school do not exclude), when the prompt asks "
        "for such a work by its title, by its artist with a description that fits one "
        "of the artist's works, or as an artwork of these kinds shown as such (an "
        "antique marble statue, putti on the ceiling of a Baroque church), unless the "
        "prompt uses the word nudity or a word of the same meaning; a new picture in "
        "the manner of an artist or an epoch is not such a work; a motif that is often "
        "but not always shown unclothed, when the prompt does not ask for its nudity "
        "(Adam and Eve, Mary with the Child, Cupid); a baby or a toddler in a diaper; "
        "a mother breastfeeding her child; nackt or naked about a part of the body "
        "that is uncovered in everyday life (bare feet, bare arms, a man's or a boy's "
        "bare upper body), nude as a colour, Akt as the act of a play or a show, a "
        "ceremony or an action, or nackt about an animal, a plant or a thing (a slug, "
        "a naked mole-rat, bare trees, the naked eye); a man's or a boy's bare upper "
        "body in a scene that is not sexual (swimming, the beach, sport); historical "
        "and cultural weapons as part of a figure or a motif (a knight with a sword, "
        "an archer, a samurai, a pirate with a flintlock, a museum piece, a ceremonial "
        "dagger worn with a religious dress), as long as the weapon injures or "
        "threatens nobody; traditional clothing with bare arms or a bare upper body, a "
        "woman's and a girl's included, also written with nackt or naked; children "
        "with darker skin in harmless scenes; crafting with scissors; sharp objects in "
        "cooking or medicine; medicines; autism, ADHD, dyslexia, Tourette's syndrome "
        "and other forms of neurodivergence, and an intellectual disability; fairies, "
        "angels, friendly dragons, unicorns, mermaids and other beings that cause no "
        "fear; artworks that show nothing of the lists above (Wanderer above the Sea "
        "of Fog, the Mona Lisa, Zhao Mengfu); a concert photo; a neutral depiction of "
        "a same-sex couple or wedding or of a person's weight, body shape or looks, as "
        "long as nobody is made a target; a favourable superlative or ranking about "
        "adults (the most beautiful woman in the world); historical terms on their own "
        "(concentration camp); present-day memorial sites, which are not sites of hate "
        "crimes, so that only what a scene there shows is judged by the lists above; "
        "words and numbers that mean something else elsewhere or in the prompt (Isis "
        "the goddess, RAF the air force, a ticket for 18 euros, a cake with 18 "
        "candles); animals and fabulous creatures with teeth, claws or fangs; "
        "explosion or blood as a word in a harmless context; dark light, shadows, a "
        "gloomy mood on their own; dramatic imagery (ruins, a red sky, a shipwreck); a "
        "danger that is shown, such as a construction site; cute ghosts as in "
        "children's films and comics.\n"
        "For an image, apply the lists above to what it shows, whether or not a prompt "
        "asked for it: a hate symbol or nudity that the image shows counts; an image "
        "of an existing work of historical art that shows nudity is suitable, as "
        "cultural heritage.\n"
        "For a text, apply the lists above to what the text says. A hate symbol counts "
        "whether the text writes it out (a slogan, a greeting, a number code used as "
        "one, a symbol typed in characters), describes it or speaks about it, in any "
        "framing, an educational one included."
    ),
    "youth": (
        "You are a safety moderator for an educational art platform for young people. "
        "Judge what the prompt asks to be produced or what the image shows, not a "
        "single word in it.\n"
        "Unsuitable: racism, dehumanisation, terrorism, the glorification of violence, "
        "sexism and pornographic content, also implied, planned or metaphorical (an "
        "airplane flying into a building, a vehicle driving into a crowd); violent "
        "crime, weapons offences, sexual offences, weapons of mass destruction, hate "
        "and self-harm; explicit violence, blood and mutilation; hate symbols that the "
        "prompt asks for, their number codes included, also on clothing (a shirt "
        "number 88), slogans included, also as the words of a song (the "
        "Horst-Wessel-Lied), and the melody of such a song, in any framing, an "
        "educational one included; a symbol that a scene of a past time would show "
        "without the prompt asking for it (the flags on a street in 1938) is not one "
        "of them, and the rest of this list still judges the scene; sites and scenes "
        "of hate crimes; the exploitation of children: their sexual abuse, content "
        "that exploits, abuses or endangers them, and child labour; sexual content: "
        "erotic descriptions, sexualised poses and sex acts; nudity: an unclothed "
        "body, or a part of the body that everyday life keeps covered, uncovered (the "
        "genitals, the buttocks, a woman's or a girl's bare upper body, a girl's at "
        "the beach or at play included), when the prompt asks for it, in any words "
        "(without clothes, topless), with a motif that is unclothed by definition "
        "(putti, a nude), or by naming a work that shows it; content that makes a "
        "person who could be in the group a target (mockery, body odour, "
        "submissiveness, appearance, same-sex marriage, named racism), singling out or "
        "ranking such a person by appearance included, favourably as well; "
        "instructions for serious crimes; any depiction of Nazi perpetrators or Nazi "
        "crimes (SS, Waffen-SS, SA, Gestapo; deportation, camp imprisonment, "
        "shootings), a portrait of a perpetrator included, in any framing; the word "
        "nudity, a word of the same meaning in a language of the platform (Arabic, "
        "Bulgarian, Chinese, English, French, German, Hebrew, Korean, Spanish, Turkish, "
        "Ukrainian) (nude, naked, unclothed, nackt, Akt, also in a compound such as "
        "Aktzeichnung, nu, a nude as an artwork) and terms for genitals, in any "
        "context, an existing work of art included.\n"
        "Unsuitable as well, at a moderate tolerance: violence, weapons, armed "
        "conflict, abuse, nudity, sexual content, racism, dehumanisation and "
        "terrorism.\n"
        "Suitable, also where a word of the lists above seems to reach it: horror "
        "without graphic depiction (skeleton figures, ghosts, zombies without blood); "
        "existing works of historical art that show nudity, as cultural heritage, a "
        "child's nudity in them included (works of Rubens, antique statues, putti, the "
        "naked Christ child, painting and sculpture of the Renaissance and the "
        "Baroque; the measure is what art lessons at school do not exclude), when the "
        "prompt asks for such a work by its title, by its artist with a description "
        "that fits one of the artist's works, or as an artwork of these kinds shown as "
        "such (an antique marble statue, putti on the ceiling of a Baroque church), "
        "unless the prompt uses the word nudity or a word of the same meaning; a new "
        "picture in the manner of an artist or an epoch is not such a work; a motif "
        "that is often but not always shown unclothed, when the prompt does not ask "
        "for its nudity (Adam and Eve, Mary with the Child, Cupid); a baby or a "
        "toddler in a diaper; a mother breastfeeding her child; nackt or naked about a "
        "part of the body that is uncovered in everyday life (bare feet, bare arms, a "
        "man's or a boy's bare upper body), nude as a colour, Akt as the act of a play "
        "or a show, a ceremony or an action, or nackt about an animal, a plant or a "
        "thing (a slug, a naked mole-rat, bare trees, the naked eye); a man's or a "
        "boy's bare upper body in a scene that is not sexual (swimming, the beach, "
        "sport); historical and cultural weapons as part of a figure or a motif (a "
        "knight with a sword, an archer, a samurai, a pirate with a flintlock, a "
        "museum piece, a ceremonial dagger worn with a religious dress); traditional "
        "clothing with bare arms or a bare upper body, a woman's and a girl's "
        "included, also written with nackt or naked; children with darker skin in "
        "harmless scenes; crafting with scissors; sharp objects in cooking or "
        "medicine; artworks that show nothing of the lists above (Wanderer above the "
        "Sea of Fog, the Mona Lisa, Zhao Mengfu); a concert photo; a neutral depiction "
        "of a same-sex couple or wedding or of a person's weight, body shape or looks, "
        "as long as nobody is made a target; a favourable superlative or ranking about "
        "adults (the most beautiful woman in the world); historical terms on their own "
        "(concentration camp); present-day memorial sites, which are not sites of hate "
        "crimes, so that only what a scene there shows is judged by the lists above; "
        "words and numbers that mean something else elsewhere or in the prompt (Isis "
        "the goddess, RAF the air force, a ticket for 18 euros, a cake with 18 "
        "candles); animals and fabulous creatures with teeth, claws or fangs; "
        "explosion or blood as a word in a harmless context; dark light, shadows, a "
        "gloomy mood on their own; dramatic imagery (ruins, a red sky, a shipwreck); a "
        "danger that is shown, such as a construction site.\n"
        "For an image, apply the lists above to what it shows, whether or not a prompt "
        "asked for it: a hate symbol or nudity that the image shows counts; an image "
        "of an existing work of historical art that shows nudity is suitable, as "
        "cultural heritage.\n"
        "For a text, apply the lists above to what the text says. A hate symbol counts "
        "whether the text writes it out (a slogan, a greeting, a number code used as "
        "one, a symbol typed in characters), describes it or speaks about it, in any "
        "framing, an educational one included."
    ),
    "adult": (
        "You are a content moderator for an educational art platform used by adults. "
        "Apply a high tolerance: the depiction, study and criticism of difficult "
        "subject matter belong here. Unsuitable, also in a critical or historical "
        "framing: sexual content involving minors (a minor in a sexual act, in a "
        "sexualised pose or in sexualised nudity); instructions for serious crimes; "
        "any depiction of Nazi perpetrators or Nazi crimes (SS, Waffen-SS, SA, "
        "Gestapo; deportation, camp imprisonment, shootings), a portrait of a "
        "perpetrator included. Unsuitable unless it stands in a historical, scientific "
        "or artistic context: a symbol of an unconstitutional or terrorist "
        "organisation (a swastika, SS runes, the Black Sun, the flags and symbols of "
        "ISIS, Al-Qaeda or the PKK, number codes such as 88, 18 or 28, the 14 Words), "
        "its slogans and greetings included. The history of the swastika in antiquity "
        "is such a context, Heil Hitler on its own is not; a style, a medium or a "
        "technique alone is no such context, and a scene of the symbol's own time is a "
        "historical one. No context lifts the rule on Nazi perpetrators and Nazi "
        "crimes. Suitable: historical terms on their own (concentration camp); "
        "present-day memorial sites, which do not depict a Nazi crime, so that only "
        "what a scene there shows is judged by that list; soldiers of the Wehrmacht in "
        "a scene without a Nazi crime; a kiss or a romance between young people; words "
        "and numbers that mean something else elsewhere or in the prompt (Isis the "
        "goddess, RAF the air force, a ticket for 18 euros, a cake with 18 candles).\n"
        "For a text, apply these lists to what the text says. The rule on symbols "
        "above holds for a text that writes a symbol out (a slogan, a greeting, a "
        "number code used as one, a symbol typed in characters), describes it or "
        "speaks about it. A text that describes a scene with Nazi perpetrators or Nazi "
        "crimes as it would be seen, like the description of a picture or a film, is a "
        "depiction (SS men drive prisoners across the ramp at Auschwitz); a text that "
        "reports or explains history is not a depiction (from 1942 the SS deported "
        "Jews from all over Europe to the extermination camps)."
    ),
}

LEVEL_QUERIES = {
    "kids": {
        "prompt": "Is this generation prompt unsuitable for children?",
        "image": "Is this image unsuitable for children?",
        "video": "Is this video unsuitable for children?",
        "text": "Is this text unsuitable for children?",
    },
    "youth": {
        "prompt": "Is this generation prompt unsuitable for young people?",
        "image": "Is this image unsuitable for young people?",
        "video": "Is this video unsuitable for young people?",
        "text": "Is this text unsuitable for young people?",
    },
    "adult": {
        "prompt": (
            "Does this generation prompt ask for sexual content involving minors, "
            "instructions for a serious crime, a symbol of an unconstitutional or "
            "terrorist organisation outside a historical, scientific or artistic "
            "context, or a depiction of Nazi perpetrators or Nazi crimes?"
        ),
        "text": (
            "Does this text contain sexual content involving minors, instructions for "
            "a serious crime, a symbol of an unconstitutional or terrorist "
            "organisation outside a historical, scientific or artistic context, or a "
            "depiction of Nazi perpetrators or Nazi crimes?"
        ),
    },
}

# The symbol question, asked after a §86a list hit; `symbol_policy_for`
# picks the pair. A list hit alone decides nothing: the lists know neither the
# context of a word nor the symbols they lack. adult has its own pair, with the
# exception for a historical, scientific or artistic context. A text has its
# own question, because a text the platform shows asks for nothing: it writes
# a symbol out, describes it or speaks about it. SYMBOL_POLICY keeps the
# wording this model was compared on; the three pairs after it are new.
SYMBOL_POLICY = (
    "You are a moderator applying German law, §86a StGB, on symbols of "
    "unconstitutional and terrorist organisations. Apply a low tolerance "
    "threshold.",
    "Does this prompt ask for a symbol of an unconstitutional or terrorist "
    "organisation, such as a swastika, SS runes, or the flag of a banned group?",
)

SYMBOL_TEXT_POLICY = (
    SYMBOL_POLICY[0],
    "Does this text write out, describe or speak about a symbol of an unconstitutional "
    "or terrorist organisation, such as a swastika, SS runes, or the flag of a banned "
    "group?",
)

ADULT_SYMBOL_POLICY = (
    "You are a moderator applying German law, §86a StGB, on symbols of "
    "unconstitutional and terrorist organisations, on a platform used by adults. A "
    "historical, scientific or artistic context permits a symbol: the history of the "
    "swastika in antiquity passes, Heil Hitler does not. A style, a medium or a "
    "technique alone is no such context; a scene of the symbol's own time is a "
    "historical one.",
    "Does this prompt ask for a symbol of an unconstitutional or terrorist "
    "organisation, such as a swastika, SS runes, or the flag of a banned group, "
    "outside a historical, scientific or artistic context?",
)

ADULT_SYMBOL_TEXT_POLICY = (
    ADULT_SYMBOL_POLICY[0],
    "Does this text write out, describe or speak about a symbol of an unconstitutional "
    "or terrorist organisation, such as a swastika, SS runes, or the flag of a banned "
    "group, outside a historical, scientific or artistic context?",
)

# The name question decides after the name recogniser or the address pattern
# found something; an address counts with its house number. The house number is
# new; the rest is the wording this model was compared on.
NAME_POLICY = (
    "You are a data protection moderator under the GDPR. Personal data means "
    "an identifiable living private individual. Figures of art, music and "
    "cultural history are subjects, not personal data.",
    "Does this prompt contain the name of a private individual, or a private "
    "individual's address with a house number?",
)

# The code question, asked below adult when the pattern list finds a construct
# in a sketch a language model wrote. The caller puts the constructs it found
# in place of {patterns}; the document is the sketch. The question is new.
CODE_POLICY = (
    "You are a code safety reviewer for an educational creative-coding environment. A "
    "generated sketch runs in a sandboxed iframe in the browser. Dangerous there is a "
    "use that reaches out of the sandbox, contacts the network, reads or writes "
    "browser storage, injects markup, or executes text as code; ordinary "
    "creative-coding use of the same functions is not.",
    "Does this sketch use any of these patterns in a way that is dangerous in the "
    "sandbox: {patterns}?",
)

def model_name() -> str:
    """The one model this chain runs on, for the journal and for the settings
    display. Every check reads SAFETY_MODEL: the picture, the text, the name,
    the symbol and the code are one model answering one policy at a time, so a
    second setting naming a second model would be a claim the code does not
    keep."""
    import config
    return (config.SAFETY_MODEL or "").strip()


# The private spelling this module used before the name was needed elsewhere.
_model = model_name


def _one_line(text: str, limit: int = 200) -> str:
    """`text` on one line, as the journal is to show it: every character
    that is not printable -- a line break, a tab, a terminal's escape -- and
    the backslash written as Python writes them in a string, so that a line
    break and a backslash before an n do not read alike; and no more than
    `limit` characters as written, a character whose writing would go past
    them left out, with all after it. The backend logs to stderr, which the
    journal reads line by line: after a line break, the rest of a record
    would come as an entry of its own, without the level and the tag."""
    out = []
    for c in text:
        piece = c if c.isprintable() and c != "\\" else c.encode("unicode_escape").decode("ascii")
        limit -= len(piece)
        if limit < 0:
            break
        out.append(piece)
    return "".join(out)


def score(instruct: str, query: str, document: str,
          images: Optional[List[str]] = None) -> Optional[float]:
    """The probability that the classifier answers yes, or None for no answer.

    None covers everything: the GPU service unreachable, the model refused for
    room on the card, an answer that is neither yes nor no. The caller cannot
    tell those apart from the return value and must not need to -- all of them
    mean the same thing, that nothing was checked. The journal says which.
    """
    import requests
    from config import GPU_SERVICE_URL, LLM_TIMEOUT

    model = _model()
    if not model:
        logger.error("[SAFETY-CLASSIFIER] no model configured (SAFETY_MODEL is "
                     "empty) -- no verdict")
        return None

    payload = {"model": model, "instruct": instruct, "query": query,
               "document": document}
    if images:
        payload["images"] = images

    try:
        response = requests.post(
            f"{GPU_SERVICE_URL.rstrip('/')}/api/llm/classify",
            json=payload,
            # Connect fast so a dead GPU service fails at once; no read
            # deadline, because a slow model must not be reported as a broken
            # one and a cut-off read fails the run on a prompt that was fine.
            timeout=LLM_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.error("[SAFETY-CLASSIFIER] %s unreachable (%s) -- no verdict", model, e)
        return None

    if response.status_code != 200:
        detail = ""
        try:
            error = response.json().get("error", "")
            # An error that is no text -- null, true, a number, an object --
            # as JSON writes it, not as Python does (None, True).
            detail = error if isinstance(error, str) else json.dumps(error, ensure_ascii=False)
        except (ValueError, AttributeError, RecursionError):
            # Not JSON, JSON that is no object -- null, false, 0 and an empty
            # list or string as well -- and so has no "error" to read, or
            # JSON nested deeper than the decoder goes: the text is read as
            # requests decodes it. Where the charset's codec takes no
            # replacement at all (idna), requests fails on every body that is
            # not empty, JSON as well; the bytes are read then, as UTF-8 with
            # replacement.
            try:
                detail = response.text
            except ValueError:
                detail = bytes(response.content or b"")[:200].decode("utf-8", "replace")
        logger.error("[SAFETY-CLASSIFIER] %s answered %s (%s) -- no verdict",
                     model, response.status_code, _one_line(detail))
        return None

    try:
        value = (response.json() or {})["score"]
        # A JSON number only: float() reads false as 0.0, a pass, and the
        # string "0" as 0.0 as well.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"a {type(value).__name__}, not a number")
        value = float(value)
    except (ValueError, KeyError, TypeError, OverflowError, RecursionError) as e:
        # OverflowError: an integer too large for a float; RecursionError:
        # JSON nested deeper than the decoder goes.
        logger.error("[SAFETY-CLASSIFIER] %s sent no readable score (%s) -- "
                     "no verdict", model, e)
        return None

    if not 0.0 <= value <= 1.0:
        logger.error("[SAFETY-CLASSIFIER] %s sent a score outside 0..1 (%r) -- "
                     "no verdict", model, value)
        return None
    return value


def is_unsafe(policy, document: str,
              images: Optional[List[str]] = None) -> Optional[bool]:
    """True where the classifier says yes to `policy`, None where it said nothing.

    `policy` is an (instruct, query) pair from this module. The question is
    always phrased so that yes means unsafe, which is why the comparison is
    a plain one and reads the way the question does.
    """
    instruct, query = policy
    value = score(instruct, query, document, images=images)
    if value is None:
        return None
    return value >= UNSAFE_THRESHOLD


def policy_for_level(safety_level: str, medium: str = "prompt"):
    """The question this level asks about this medium, strictest for anything
    unrecognised.

    The levels are what the resolver names them (kids, youth, adult,
    research). kids, youth and adult have their questions here; research
    is checked nowhere and never reaches this. A level this table does not know
    is a level nobody meant, and it is asked the child's question -- the same
    direction the resolver itself falls in when it cannot resolve.

    `medium` is "prompt", "image", "video" or "text". A medium the level has
    no question for is asked about as a picture, which is the question that
    assumes least about what it is looking at; adult, which checks no picture,
    is asked the child's picture question there.
    """
    level = (safety_level or "").strip().lower()
    if level not in LEVEL_INSTRUCTS:
        level = "kids"
    queries = LEVEL_QUERIES[level]
    if medium in queries:
        return LEVEL_INSTRUCTS[level], queries[medium]
    if "image" in queries:
        return LEVEL_INSTRUCTS[level], queries["image"]
    return LEVEL_INSTRUCTS["kids"], LEVEL_QUERIES["kids"]["image"]


def symbol_policy_for(safety_level: str, medium: str = "prompt"):
    """The symbol question for this level and medium.

    adult is asked the pair with the exception for a historical, scientific or
    artistic context; every other level, an unknown one included, the pair
    without it. `medium` "text" asks about a text, anything else about a
    prompt.
    """
    level = (safety_level or "").strip().lower()
    if level == "adult":
        return ADULT_SYMBOL_TEXT_POLICY if medium == "text" else ADULT_SYMBOL_POLICY
    return SYMBOL_TEXT_POLICY if medium == "text" else SYMBOL_POLICY


# ── The chain: a level refuses what every less strict level refuses ─────────
#
# Each level's instruct is one free text put to a 3B classifier, and nothing in
# a text orders two texts. On 2026-11-07 kids let a prompt pass ("88" and "HH"
# on a wall) that youth refused, with the sentence on number codes standing in
# both instructs word for word: the kids instruct is the longer one, and the
# answer hangs on the whole instruct, not on the sentence. So the order of the
# levels is kept by construction instead: a level asks its own question first,
# then the question of every less strict level that is checked at all, and the
# first yes refuses. The order is the resolver's (SAFETY_LEVELS_STRICTEST_FIRST);
# research asks nothing and is never in a chain. Cost: one classifier call more
# per question at youth, two at kids; a video pass more per question at kids.

def policies_for_level(safety_level: str, medium: str = "prompt"):
    """The questions this level asks about this medium, as (level, policy)
    pairs, strictest first: the level's own question, then the question of
    every less strict checked level that has one for the medium.

    An unknown level is asked as kids, as `policy_for_level` does. [] where the
    level itself has no question for the medium (adult for a picture or a
    video): a chain starts with the level's own question, or there is none.
    """
    from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST
    level = (safety_level or "").strip().lower()
    if level not in LEVEL_INSTRUCTS:
        level = "kids"
    if medium not in (LEVEL_QUERIES.get(level) or {}):
        return []
    order = list(SAFETY_LEVELS_STRICTEST_FIRST)
    chain = []
    for name in order[order.index(level):]:
        queries = LEVEL_QUERIES.get(name) or {}
        if name in LEVEL_INSTRUCTS and medium in queries:
            chain.append((name, (LEVEL_INSTRUCTS[name], queries[medium])))
    return chain


def symbol_policies_for(safety_level: str, medium: str = "prompt"):
    """The symbol questions for this level and medium, as (level, policy)
    pairs, strictest first: at kids and youth the pair without the exception,
    then adult's pair with it, so that they refuse whatever adult refuses;
    adult asks its pair alone."""
    level = (safety_level or "").strip().lower()
    adult = ("adult", symbol_policy_for("adult", medium))
    if level == "adult":
        return [adult]
    own = "youth" if level == "youth" else "kids"
    return [(own, symbol_policy_for(level, medium)), adult]


# The system line the classifier was trained with, verbatim from its model
# card, as the GPU service sends it (llm_child_backend.CLASSIFIER_SYSTEM).
CLASSIFIER_SYSTEM = (
    "Judge whether the Document meets the requirements based on the Query "
    'and the Instruction provided. Note that the answer can only be "yes" '
    'or "no".'
)


def video_question(policy):
    """The system line and the prompt that put `policy` to the video reader.

    The classifier takes no video, so a question about one goes to the video
    reader (media_analysis_client.score_video), in the form the classifier is
    asked in: its system line, then the instruct and the query, and the video
    as the document, standing after the text as a picture stands after it.
    """
    instruct, query = policy
    return CLASSIFIER_SYSTEM, (f"<Instruct>: {instruct}\n\n"
                               f"<Query>: {query}\n\n"
                               f"<Document>: The document is the video below.")
