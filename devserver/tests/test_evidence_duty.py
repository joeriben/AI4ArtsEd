"""evidence_duty: Resona's internal Belegpflicht - lexicon, validator, stripping.
Hardened per the 2026-07-17 adversarial review (24 agents, 15 confirmed findings)."""
from my_app.services import evidence_duty as ED


DOCS = [
    ("kite-and-wormsley-2020-invitation", "An Invitation ...", "Kite, Alisha B. Wormsley"),
    ("abdilla-et-al-2020-indigenous-protocol", "Indigenous Protocol and AI",
     "Jason Edward Lewis, Indigenous Protocol and Artificial Intelligence Working Group"),
    ("unesco-guidance-2023", "Guidance", "UNESCO"),
    ("tuck-yang-2012", "Decolonization is not a metaphor", "Eve Tuck and K. Wayne Yang"),
]
GLOSSARY = [
    ("Indigenous protocol", "abdilla-et-al-2020-indigenous-protocol"),
    ("Decolonizing Arts Education", "morsch-2021-decolonizing"),
    ("art theory", "doc-art-theory"),
    ("Arts Education", "unesco-framework"),  # everyday self-description -> stoplist
    ("Blick", "meyer-2019"),                 # single word - never a trigger
    ("AI + X", "unesco-cft"),                # too short - never a trigger
]
LEX = ED.build_lexicon(DOCS, GLOSSARY)


def test_lexicon_surnames_terms_and_stoplist():
    assert "Kite" in LEX["surnames"]
    assert "Wormsley" in LEX["surnames"]
    assert "Lewis" in LEX["surnames"]
    assert "UNESCO" in LEX["surnames"]
    # 'and'-joined author fields are split (adversarial review finding)
    assert "Tuck" in LEX["surnames"] and "Yang" in LEX["surnames"]
    # lead author derived from bibliographic doc_id (abdilla-et-al-...)
    assert "Abdilla" in LEX["surnames"]
    # organisation author parts (5+ words) never become surnames
    assert "Group" not in LEX["surnames"]
    assert "indigenous protocol" in LEX["terms"]
    assert "decolonizing arts education" in LEX["terms"]
    assert "art theory" in LEX["terms"]
    # everyday platform vocabulary is stoplisted, single/short terms excluded
    assert "arts education" not in LEX["terms"]
    assert "blick" not in LEX["terms"]
    assert "ai + x" not in LEX["terms"]


def test_unbacked_empty_and_truncated_src_markers():
    v = ED.validate("The paper says X. [src: some-doc]", ledger=[], lexicon=LEX)
    assert len(v) == 1 and "not backed by anything you opened" in v[0]
    v = ED.validate("Claim. [src: ]", ledger=[("web", "https://x.example/page")],
                    lexicon=LEX)
    assert len(v) == 1 and "empty or truncated" in v[0]
    v = ED.validate("Claim. [src: h]", ledger=[("web", "https://x.example/page")],
                    lexicon=LEX)
    assert len(v) == 1 and "empty or truncated" in v[0]


def test_web_refs_need_the_exact_opened_page():
    ledger = [("web", "https://www.explore-vc.org")]
    v = ED.validate("Seen. [src: https://www.explore-vc.org/anything/i/invent]",
                    ledger=ledger, lexicon=LEX)
    assert len(v) == 1 and "not backed" in v[0]
    v = ED.validate("Seen. [src: https://www.explore-vc.org/]",
                    ledger=ledger, lexicon=LEX)
    assert v == []


def test_backed_doc_marker_passes():
    ledger = [("doc", "kite-and-wormsley-2020-invitation")]
    v = ED.validate("Kite and Wormsley invite artists to dream. "
                    "[src: kite-and-wormsley-2020-invitation]",
                    ledger=ledger, lexicon=LEX)
    assert v == []


def test_named_scholar_without_reading_is_violation():
    v = ED.validate("As Kite argues, protocols matter.", ledger=[], lexicon=LEX)
    assert any("Kite" in x and "read_knowledge" in x for x in v)
    assert any("kite-and-wormsley-2020-invitation" in x for x in v)


def test_german_genitive_and_allcaps_count_as_mentions():
    v = ED.validate("In Abdillas Protokollen steckt viel. [own]",
                    ledger=[], lexicon=LEX)
    assert any("Abdilla" in x for x in v)
    v = ED.validate("Kites Arbeit zeigt das. [own]", ledger=[], lexicon=LEX)
    assert any("Kite" in x for x in v)
    v = ED.validate("UNESCOs Rahmen sagt dazu etwas. [own]", ledger=[], lexicon=LEX)
    assert any("UNESCO" in x for x in v)
    v = ED.validate("KITE hat dazu gearbeitet.", ledger=[], lexicon=LEX)
    assert any("Kite" in x for x in v)


def test_lowercase_kite_the_object_is_no_trigger():
    v = ED.validate("We could build a kite from paper and string.",
                    ledger=[], lexicon=LEX)
    assert v == []


def test_viewed_run_does_not_license_discourse():
    # THE critical bypass from the review: a run marker must not unlock lecturing
    v = ED.validate("Ich habe euer Bild angesehen [src: run_4711]. "
                    "Bei kultureller Aneignung ist Vorsicht geboten.",
                    ledger=[("run", "run_4711")], lexicon=LEX)
    assert len(v) == 1 and "kulturelle" in v[0].lower()


def test_discourse_backed_by_actual_reading_even_without_marker():
    # model read a doc but forgot the notation - substance was delivered
    v = ED.validate("Cultural appropriation is worked through here concretely.",
                    ledger=[("doc", "unesco-guidance-2023")], lexicon=LEX)
    assert v == []


def test_bias_and_synonym_discourses_trigger():
    v = ED.validate("Algorithmic bias shapes these systems. [own]",
                    ledger=[], lexicon=LEX)
    assert len(v) == 1
    v = ED.validate("Aboriginal knowledge systems are marginalized; "
                    "scholars argue this is well established.",
                    ledger=[], lexicon=LEX)
    assert len(v) == 1


def test_echo_of_the_educators_own_words_is_exempt():
    user = "Wir wollen mit indigener Kunst arbeiten - was meinst du?"
    v = ED.validate("Indigene Kunst also - was zieht die Gruppe dahin?",
                    ledger=[], lexicon=LEX, user_text=user)
    assert v == []
    # but a named scholar is never exempt
    v = ED.validate("Kite sagt dazu einiges.", ledger=[], lexicon=LEX,
                    user_text="Was sagt eigentlich Kite dazu?")
    assert any("Kite" in x for x in v)


def test_glossary_terms_match_on_word_boundaries():
    v = ED.validate("These smart theory tools help us plan.",
                    ledger=[], lexicon=LEX)
    assert v == []
    v = ED.validate("Art theory matters for this session.",
                    ledger=[], lexicon=LEX)
    assert len(v) == 1


def test_the_literature_is_no_longer_a_trigger():
    v = ED.validate("Put the literature on the table so everyone can browse.",
                    ledger=[], lexicon=LEX)
    assert v == []


def test_strip_markers_is_local_and_preserves_formatting():
    raw = ("Kite invites artists to dream [src: kite-and-wormsley-2020-invitation] , "
           "and I would begin small [own] .")
    clean = ED.strip_markers(raw)
    assert "[src:" not in clean and "[own]" not in clean
    assert "dream," in clean and "small." in clean
    # no global whitespace normalization (review: nested lists / code indents)
    listy = "- step one\n  - nested item\n    code_indent()\n\n\nEnd."
    assert ED.strip_markers(listy) == listy
    assert ED.strip_markers("plain text, untouched.") == "plain text, untouched."


def test_correction_message_puts_reading_first():
    msg = ED.correction_message(["- x"])
    assert "NOT seen your draft" in msg
    assert "reading comes first" in msg


def test_prompt_carries_the_duty():
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT, RESONA_PLANNING_BLOCK
    assert "INTERNAL EVIDENCE DUTY" in RESONA_CORE_PROMPT
    assert "[own]" in RESONA_CORE_PROMPT
    # planning asks after the counterpart because the form depends on it.
    # Whitespace-normalised: the prompt is hard-wrapped and a reflow must not
    # silently disarm the check.
    assert "genuine interest in who is on the other side" in " ".join(
        RESONA_PLANNING_BLOCK.split()
    )


# --- the third move: looking is owed, finding is not -----------------------

def test_empty_search_grounds_a_discourse_claim():
    # The shelf holds nothing on the topic, the search ran and came back
    # empty, Resona stands on its own reasoning. Before this, validate()
    # knew only "opened" or "violation", so the only ways out were a
    # question or a citation that did not fit - and it took the second.
    v = ED.validate("Cuteness carries its own colonial history, I suspect. [own]",
                    ledger=[("miss", "Niedlichkeit Bildkulturen")], lexicon=LEX)
    assert v == []


def test_empty_search_never_licenses_an_unopened_shelf_author():
    # The surname rule is per-author and does NOT relax: missing on one
    # query is no warrant for invoking someone whose text sits unopened.
    v = ED.validate("Kite argues that protocol precedes design. [own]",
                    ledger=[("miss", "cuteness")], lexicon=LEX)
    assert len(v) == 1 and "Kite" in v[0]


def test_a_viewed_run_is_still_not_a_search():
    # Guards the fix against over-reach: only a real ('miss', query) entry
    # grounds a discourse - a run remains inert.
    v = ED.validate("Bei kultureller Aneignung ist Vorsicht geboten.",
                    ledger=[("run", "run_4711")], lexicon=LEX)
    assert len(v) == 1


def test_discourse_violation_asks_for_looking_not_finding():
    v = ED.validate("Cultural appropriation is a risk here.", ledger=[], lexicon=LEX)
    assert len(v) == 1
    assert "without having looked" in v[0]
    assert "comes back empty" in v[0]


def test_correction_message_offers_the_escape_validate_actually_honours():
    # The old wording promised "only if the shelf truly holds nothing ...
    # stand on [own]", which validate() did not implement - prompt and
    # check contradicted each other and the model was cornered into a
    # misattribution. They must now say the same thing.
    msg = ED.correction_message(["- x"])
    assert "comes back empty" in msg and "[own]" in msg


def test_a_question_opens_a_turn_and_never_closes_one():
    # The core prompt used to ban the service question
    # ("Soll ich ...?") and then license the situation-reaching one
    # "anywhere, including at the end" - which is exactly the trailing
    # follow-up. Questions open a turn now; the work ends it.
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT as P
    assert "including at the end" not in P
    assert "at the opening of a" in P
    assert "never closes one" in P
    # the service-question ban stays. Its example is English: prompts are
    # English, and test_no_prefabricated_categories_offered
    # forbids German example sentences in the core. This assertion still
    # demanded "Soll ich ...?" and has been red since 5eb26386 removed it.
    assert "Shall I" in P
