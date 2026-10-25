#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which parts of this platform support which measures of the AILit framework,
and how. One source, five outputs, so nothing drifts:

  docs/OECD_AILIT_ABDECKUNG.md               German, by competence and level
  docs/AILIT_ORTE_ZUORDNUNG.md               German, by part of the platform
  docs/AILIT_ZUORDNUNGSTABELLE.md / .tsv     the plain table by part, keyword phrases
  devserver/my_app/knowledge/ailit_coverage.json   read by build_platform_items.py,
                                             so Help carries a page's measures
  devserver/exports/ailit_coverage.sqlite    gitignored, for queries

The table starts from the platform, because its purpose is to inform Help
about the active page: the rows stand by part, mode, instrument or
cross-cutting function, and under each part the measures it supports; what no
part carries closes the table.

The question each row answers: does a part of the platform SUPPORT a measure
the OECD describes, and if so how, and which practical scenario shows it. The
measures are the framework's own "In the Classroom" scenarios, one per
competence and level, 57 in all; they are human-led activities, and the
platform is judged as a TOOL for them. An earlier frame had the rows judge
whether the platform itself performs the learner action a level names, which
judged the platform as a pedagogical actor. That frame is gone.

Reads:  docs/ailit/learner_expectations.tsv   verbatim statements and levels
        docs/ailit/classroom_scenarios.tsv    verbatim "In the Classroom" texts
        docs/ailit/unterstuetzung.tsv         one row per part and measure, by part
Run:    python3 devserver/scripts/build_ailit_support.py
"""
import csv
import json
import sqlite3
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP_TSV = ROOT / 'docs' / 'ailit' / 'learner_expectations.tsv'
SCEN_TSV = ROOT / 'docs' / 'ailit' / 'classroom_scenarios.tsv'
SUP_TSV = ROOT / 'docs' / 'ailit' / 'unterstuetzung.tsv'
OUT_MD = ROOT / 'docs' / 'OECD_AILIT_ABDECKUNG.md'
OUT_PLACES = ROOT / 'docs' / 'AILIT_ORTE_ZUORDNUNG.md'
OUT_TABLE_MD = ROOT / 'docs' / 'AILIT_ZUORDNUNGSTABELLE.md'
OUT_TABLE_TSV = ROOT / 'docs' / 'AILIT_ZUORDNUNGSTABELLE.tsv'
OUT_JSON = ROOT / 'devserver' / 'my_app' / 'knowledge' / 'ailit_coverage.json'
OUT_SQLITE = ROOT / 'devserver' / 'exports' / 'ailit_coverage.sqlite'

LEVELS = ('Basic', 'Intermediate', 'Advanced')
STATUS = ('ja', 'angepasst', 'nein')

QUELLE_DE = ('OECD / European Union (2026), *Empowering learners for the age of AI: '
             'An AI literacy framework for primary and secondary education*, '
             'OECD Publishing, Paris, https://doi.org/10.1787/65cd27d4-en, CC BY 4.0. '
             'Wortlaut und Seitenzahlen in `docs/ailit/learner_expectations.tsv` und '
             '`docs/ailit/classroom_scenarios.tsv`, Herkunft und Lesart in '
             '`docs/ailit/QUELLE.md`.')
QUELLE_EN = ('OECD / European Union (2026), Empowering learners for the age of AI: '
             'An AI literacy framework for primary and secondary education, '
             'OECD Publishing, Paris, https://doi.org/10.1787/65cd27d4-en, CC BY 4.0')

# --- parts of the platform ----------------------------------------------------
# key -> (name_de, name_en, route, kind). The names are the labels the surface
# carries (de.ts / en.ts: the tab, the page), so a row can be read against the
# screen. Direct (/direct) stood here until 2026-09-19; the page is deprecated
# and is to be deleted, so no measure is assigned to it. The data-path
# display stood here as a function until the same day; the component was
# removed on 2026-08-16.
P = OrderedDict([
    ('flow',      ('Flow', 'Flow', '/x2x-flow', 'Modus')),
    ('workshop',  ('Together', 'Together', '/together', 'Modus')),
    ('contest',   ('Contesting', 'Contesting', '/contesting', 'Modus')),
    ('canvas',    ('Canvas', 'Canvas', '/canvas', 'Modus')),
    ('ll_overview',  ('Überblick', 'Overview', '/latent-lab/overview', 'Instrument')),
    ('ll_model',     ('Modell-Vergleich', 'Model Comparison', '/latent-lab/model-comparison', 'Instrument')),
    ('ll_census',    ('Stereotypen-Analyse', 'Stereotype Analysis', '/latent-lab/cultural-un-known', 'Instrument')),
    ('ll_vlm',       ('Bildverständnis', 'Image Understanding', '/latent-lab/image-understanding', 'Instrument')),
    ('ll_language',  ('Sprachverständnis', 'Language Understanding', '/latent-lab/language-understanding', 'Instrument')),
    ('ll_voice',     ('Stimmen-Vergleich', 'Voice Comparison', '/latent-lab/voices', 'Instrument')),
    ('ll_sysprompt', ('System Prompts', 'System Prompts', '/latent-lab/system-prompts', 'Instrument')),
    ('ll_imodels',   ('Sprachmodell-Vergleich', 'Language Model Comparison', '/latent-lab/interception-across-models', 'Instrument')),
    ('ll_itemplate', ('Wirkungsvergleich', 'Interception Scope', '/latent-lab/perspectives-on-a-template', 'Instrument')),
    ('ll_ipoles',    ('Ästhetische Pole', 'Aesthetic Poles', '/latent-lab/aesthetic-poles', 'Instrument')),
    ('ll_archaeology', ('Denoising Archaeology', 'Denoising Archaeology', '/latent-lab/denoising-archaeology', 'Instrument')),
    ('ll_mean',      ('Mean Images', 'Mean Images', '/latent-lab/mean-images', 'Instrument')),
    ('ll_attention', ('Attention Cartography', 'Attention Cartography', '/latent-lab/attention-cartography', 'Instrument')),
    ('ll_fusion',    ('Encoder Fusion', 'Encoder Fusion', '/latent-lab/encoder-fusion', 'Instrument')),
    ('ll_probing',   ('Dimension Explorer', 'Dimension Explorer', '/latent-lab/dimension-explorer', 'Instrument')),
    ('ll_algebra',   ('Concept Algebra', 'Concept Algebra', '/latent-lab/concept-algebra', 'Instrument')),
    ('ll_composable', ('Composable Diffusion', 'Composable Diffusion', '/latent-lab/composable-diffusion', 'Instrument')),
    ('ll_workbench', ('Enc. Fus. Workbench', 'Enc. Fus. Workbench', '/latent-lab/fusion-workbench', 'Instrument')),
    ('ll_bias',      ('Bias Research 1', 'Bias Research 1', '/latent-lab/bias-archaeology', 'Instrument')),
    ('ll_coref',     ('Bias Research 2', 'Bias Research 2', '/latent-lab/coreference-test', 'Instrument')),
    ('ll_repeng',    ('Representation Engineering', 'Representation Engineering', '/latent-lab/representation-engineering', 'Instrument')),
    ('ll_tokens',    ('Tokenizer', 'Tokenizer', '/latent-lab/tokenization', 'Instrument')),
    ('ll_synth',     ('Latent Audio Synth', 'Latent Audio Synth', '/latent-lab/audio-synth', 'Instrument')),
    ('ll_mmaudio',   ('MMAudio', 'MMAudio', '/latent-lab/mmaudio', 'Instrument')),
    ('ll_guidance',  ('ImageBind Guidance', 'ImageBind Guidance', '/latent-lab/imagebind-guidance', 'Instrument')),
    ('ll_reenactment', ('Re-enactment', 'Re-enactment', '/latent-lab/re-enactment', 'Instrument')),
    ('ll_lora',      ('LoRA Training', 'LoRA Training', '/latent-lab/lora-sd35', 'Instrument')),
    ('ll_loraexpl',  ('LoRA Explorer', 'LoRA Explorer', '/latent-lab/lora-explorer', 'Instrument')),
    # Cross-cutting functions: they belong to no place and act on all of them.
    # The header carries no label of its own (its lines are the energy readout
    # and the queue); the two others are named as the surface names them
    # (de.ts aiMark / gallery.title).
    ('fn_header',   ('Kopfzeile: Energie und Warteschlange', 'Header: energy and queue', 'querliegend', 'Funktion')),
    ('fn_marking',  ('KI-Kennzeichnung', 'AI marking', 'querliegend', 'Funktion')),
    ('fn_shelf',    ('Favoriten', 'Favorites', 'querliegend', 'Funktion')),
])
# The view names (what the frontend sends as "Aktive Ansicht") of the parts
# that have no entry in the catalogue platform_items.json, so Help can reach
# their measures through the coverage file (platform_items.place_for_view):
# the Vue file stems of the four modes, and for the Tokenizer the name the
# Transformers Lab writes for a tab without a context of its own
# (latent_text_lab.vue: `latent_text_lab.${activeTab}`). The Overview alone
# sets no view context and is found by the route the frontend sends instead.
VIEWS = {
    'flow': ['x2x_flow'],
    'workshop': ['resona'],
    'contest': ['ai_persona'],
    'canvas': ['canvas_workflow'],
    'll_tokens': ['latent_text_lab.tokens'],
}
# Earlier addresses a page still answers under. The overview was reachable as
# /latent-lab/intro until 2026-08-23 and keeps working under that address
# (latent_lab.vue, IDS); the frontend sends the address as it stands.
ALIASES = {
    'll_overview': ['/latent-lab/intro'],
}
KINDS = (('Modus', 'Modi'), ('Instrument', 'Instrumente'), ('Funktion', 'Querliegende Funktionen'))

# --- the 19 competences ------------------------------------------------------
# label_en is asserted against learner_expectations.tsv below.
C = [
 ('engage-1', 'Engage with AI', 1, 'KI im Alltag erkennen',
  'Rolle und Einfluss von KI in verschiedenen Zusammenhängen erkennen',
  "Recognise AI's role and influence in different contexts."),
 ('engage-2', 'Engage with AI', 2, 'Funktionsweise erklären',
  'beschreiben, wie KI-Systeme Aufgaben ausführen, in einer Sprache, die verbreitete Fehlvorstellungen ausräumt',
  'Describe how AI systems perform tasks using language that addresses and clarifies common misconceptions.'),
 ('engage-3', 'Engage with AI', 3, 'Ausgabe annehmen, ändern, verwerfen',
  'beurteilen, ob eine Ausgabe angenommen, überarbeitet oder verworfen wird',
  'Evaluate whether AI outputs should be accepted, revised or rejected.'),
 ('engage-4', 'Engage with AI', 4, 'Empfehlungssysteme durchschauen',
  'untersuchen, wie prädiktive KI-Systeme Empfehlungen geben, die Perspektiven informieren oder begrenzen können',
  'Examine how predictive AI systems provide recommendations that can inform or limit perspectives.'),
 ('engage-5', 'Engage with AI', 5, 'Energie und Ressourcen vergleichen',
  'vergleichen, wie KI-Systeme Energie und natürliche Ressourcen verbrauchen',
  'Compare how AI systems consume energy and natural resources.'),
 ('engage-6', 'Engage with AI', 6, 'Verzerrungen erklären',
  'erklären, wie KI genutzt werden könnte, um gesellschaftliche Verzerrungen zu verstärken',
  'Explain how AI could be used to amplify societal biases.'),
 ('engage-7', 'Engage with AI', 7, 'Einsatz an Werten prüfen',
  'prüfen, wie gut der Einsatz eines Systems zu ethischen Prinzipien und menschlichen Werten passt',
  'Analyse how well the use of an AI system aligns with ethical principles and human values.'),
 ('create-1', 'Create with AI', 1, 'Neue Perspektiven erkunden',
  'mit KI-Systemen neue Perspektiven und Ansätze erkunden, die auf ursprünglichen Ideen aufbauen',
  'Use AI systems to explore new perspectives and approaches that build upon original ideas.'),
 ('create-2', 'Create with AI', 2, 'Prototypen, Systemarten verbinden',
  'Ideen visualisieren, prototypisch bauen und über verschiedene KI-Arten hinweg verbinden',
  'Visualise, prototype and combine ideas using different types of AI systems.'),
 ('create-3', 'Create with AI', 3, 'Rückmeldung holen, überarbeiten',
  'generative KI so führen, dass Rückmeldung entsteht, Ergebnisse überarbeitet und Reflexion getragen wird',
  'Direct generative AI systems to elicit feedback, refine results and support reflection.'),
 ('create-4', 'Create with AI', 4, 'Authentizität und Urheberschaft',
  'analysieren, wie KI Authentizität und geistiges Eigentum wahrt oder verletzt',
  'Analyse how AI can safeguard or violate content authenticity and intellectual property.'),
 ('manage-1', 'Manage AI', 1, 'KI einsetzen oder darauf verzichten',
  'entscheiden, ob KI eingesetzt wird, je nach Art der Aufgabe',
  'Decide whether to use AI systems based on the nature of the task.'),
 ('manage-2', 'Manage AI', 2, 'Ansatz durch Vergleich wählen',
  'den passenden KI-Ansatz wählen, indem verglichen wird, wie Systeme arbeiten und wofür sie taugen',
  'Choose an appropriate AI approach for a task by comparing how different AI systems operate and what they are best suited to do.'),
 ('manage-3', 'Manage AI', 3, 'Aufgabe zerlegen',
  'ein Problem zerlegen und bestimmen, wann KI automatisiert und wann sie unterstützt',
  'Decompose a problem to determine when and how AI systems should be used to automate or augment tasks.'),
 ('manage-4', 'Manage AI', 4, 'Einsatz beobachten und bewerten',
  'den KI-Einsatz über den ganzen Prozess hinweg beobachten und bewerten',
  'Monitor and evaluate AI use throughout a problem-solving process.'),
 ('shape-1', 'Shape AI', 1, 'Zweck, Adressaten, Grenzen',
  'untersuchen, wie ein System arbeiten soll, für wen es entworfen ist und wo seine Grenzen liegen',
  'Investigate how an AI system is intended to work, whom it is designed for and what its limitations are.'),
 ('shape-2', 'Shape AI', 2, 'An eigenen Kriterien testen',
  'Systeme an eigenen Kriterien, erwarteten Ergebnissen, Testfällen und Rückmeldung bewerten',
  'Evaluate AI systems using defined criteria, expected outcomes, test cases and user feedback.'),
 ('shape-3', 'Shape AI', 3, 'Datenquellen und Informationsfluss',
  'Systeme gestalten mit Blick auf Datenquellen, Auswahl und Informationsfluss',
  'Design AI systems with attention to how data sources, selection and information flow influence behaviour and outputs.'),
 ('shape-4', 'Shape AI', 4, 'Systeme verbessern',
  'Systeme verbessern, damit sie Wohlergehen und gesellschaftlichem Nutzen dienen',
  'Improve AI systems to address and promote human well-being and societal benefit.'),
]
DOM_DE = {'Engage with AI': 'Engage', 'Create with AI': 'Create', 'Manage AI': 'Manage', 'Shape AI': 'Shape'}
COMP = OrderedDict()
for code, dom, n, kurz, label_de, label_en in C:
    COMP[f'{DOM_DE[dom]} {n}'] = dict(code=code, domain=dom, n=n, kurz_de=kurz,
                                       label_de=label_de, label_en=label_en)

# --- keyword phrases ----------------------------------------------------------
# competence -> (phrase of the competence statement, (Basic, Intermediate, Advanced)).
# Condensed from the wording in learner_expectations.tsv, nothing added; checked
# against the verbatim wording on 2026-09-19 (76 phrases, 29 corrected then).
PHRASES = {
 'Engage 1': ('Rolle und Einfluss von KI in verschiedenen Kontexten erkennen',
   ('benennen, wo im eigenen Alltag verschiedene Arten von KI vorkommen',
    'Beispiele teilen, wie KI eigene Entscheidungen und Erfahrungen zu Hause, in der Schule oder online beeinflusst hat',
    'analysieren, wie KI-Systeme Überzeugungen und Verhalten als Konsumenten, Lernende, Arbeitende und Bürger prägen können')),
 'Engage 2': ('Funktionsweise beschreiben, Fehlvorstellungen dabei ausräumen',
   ('KI als nicht-menschliches Werkzeug: Ausgaben aus Datenmustern, ohne echten Kontext oder Verstehen',
    'zutreffend beschreiben, wie ein bestimmtes KI-Werkzeug eine Aufgabe ausführt, um Fehlvorstellungen anzugehen',
    'erklären, wie verschiedene KI-Systeme arbeiten, ohne menschliche Züge oder Fähigkeiten zuzuschreiben; Wortwahl prägt Verstehen')),
 'Engage 3': ('Ausgaben bewerten: annehmen, überarbeiten oder ablehnen',
   ('Prüfbedarf verstehen, Prüfwege kennen',
    'auf Richtigkeit und Relevanz prüfen: an verlässlichen Quellen und an den Erwartungen der Aufgabe',
    'Annahme, Überarbeitung oder Ablehnung begründen')),
 'Engage 4': ('untersuchen, wie prädiktive Systeme Empfehlungen geben, die Perspektiven informieren oder begrenzen können',
   ('KI kann Nutzerdaten für Empfehlungen und Vorhersagen nutzen',
    'erwägen, wann Empfehlungen hilfreich und wann sie zu eng und zu allgemein wirken',
    'Nutzen und Nachteile datengesteuerten Informationszugangs abwägen; bedenken, wie das Weltbilder, Ideen oder Verhalten beeinflussen könnte')),
 'Engage 5': ('Energie- und Ressourcenverbrauch von KI-Systemen vergleichen',
   ('Computer und KI-Systeme brauchen Ressourcen, um zu funktionieren',
    'beschreiben, wie KI auf die Umwelt wirkt: Hardwareproduktion, Rechenzentren, Wasserverbrauch, Energieintensität',
    'analysieren, wie individuelle Entscheidungen und Entwurfs-, Einsatz- und Geschäftsentscheidungen den Energie- und Ressourcenverbrauch beeinflussen können')),
 'Engage 6': ('erklären, wie KI genutzt werden könnte, um gesellschaftliche Verzerrungen zu verstärken',
   ('Verzerrung kann in Trainingsdaten liegen und durch Entwurf, Entwicklung und Nutzung fortgeschrieben werden',
    'erklären, wie verzerrte Daten oder Entwurfsentscheidungen zu unfairen Ergebnissen für bestimmte Gruppen führen können',
    'analysieren, wie Einzelne, Unternehmen oder Institutionen KI-Systeme für bestimmte Interessen bauen und einsetzen könnten und wie diese Chancen, Darstellungen oder öffentliche Wahrnehmung prägen könnten')),
 'Engage 7': ('analysieren, wie gut der Einsatz eines Systems zu ethischen Prinzipien und menschlichen Werten passt',
   ('ethischer Einsatz hängt an mehreren Faktoren, darunter Entwurf, Entwicklung und die eigene Absicht der Nutzenden',
    'erkennen, wann KI-Einsatz unbeabsichtigte Folgen haben kann',
    'Einsatz nach mehreren ethischen Prinzipien bewerten, Abwägungen bedenken und wer profitieren oder geschädigt werden könnte')),
 'Create 1': ('mit KI neue Perspektiven und Ansätze erkunden, die auf ursprünglichen Ideen aufbauen',
   ('erkunden, wie verschiedene KI-Werkzeuge das eigene Denken erweitern oder neue Ideen anstoßen können',
    'KI-Vorschläge beim Brainstorming mit eigenen Ideen vergleichen',
    'KI-Ausgaben gezielt mit eigenen Ideen verbinden, um umfassende Lösungen und kreative Ansätze zu entwickeln')),
 'Create 2': ('Ideen mit verschiedenen Arten von KI-Systemen visualisieren, prototypisieren, kombinieren',
   ('eine Idee als Bild, Geschichte oder Modell erzeugen',
    'mit KI-Werkzeugen (Text-, Bild-, Musikgeneratoren) experimentieren, um vielfältige Ideen und verschiedene Ausgaben zu erzeugen',
    'Ausgaben mehrerer Systeme auswählen und zum Endprodukt verbinden')),
 'Create 3': ('KI lenken: Rückmeldung holen, überarbeiten, Reflexion stützen',
   ('wissen, wie KI-Systeme zu prompten sind, damit sie zutreffende Rückmeldung und hilfreiche Antworten zu einer Idee geben',
    'die eigene Arbeit im Wechsel mit KI überarbeiten; Ausgaben mit eigenen Ideen vergleichen und am eigenen Ziel messen',
    'Einfluss der Rückmeldung kritisch bewerten, eigene KI-Nutzung reflektieren')),
 'Create 4': ('analysieren, wie KI Echtheit und geistiges Eigentum schützen oder verletzen kann',
   ('Ausgabe kann geschützte Werke wiederverwenden oder kopieren, Folgen für die Urheber',
    'abwägen, wann Nennung, Erlaubnis oder Verzicht auf KI angemessen ist, und danach handeln',
    'ethische Folgen für kreative Arbeit einschätzen, Anregung von Nachbildung unterscheiden, Echtheit und Respekt vor anderen Urhebern begründen')),
 'Manage 1': ('je nach Art der Aufgabe entscheiden, ob KI eingesetzt wird',
   ('Systeme und ihre Aufgaben kennen',
    'aus KI-Wissen die Passung zur konkreten Aufgabe bestimmen',
    'bestimmen, ob KI das richtige Werkzeug ist, indem Komplexität und Bedarf an menschlichem Urteil gegen die ethischen Folgen abgewogen werden')),
 'Manage 2': ('einen passenden KI-Ansatz wählen, indem verglichen wird, wie Systeme arbeiten und wofür sie am besten taugen',
   ('erkennen, dass manche Systeme mit festen Regeln programmiert sind und andere Muster aus Daten lernen',
    'Vor- und Nachteile eines regelbasierten und eines lernenden Ansatzes für ein Problem benennen',
    'bewerten, wann KI passt: Kontext, Datenlage und -qualität, Effizienz, Transparenz, Ziele, Folgen')),
 'Manage 3': ('ein Problem zerlegen, um zu bestimmen, wann und wie KI Aufgaben automatisieren oder ergänzen soll',
   ('Art des Problems erkennen und erwägen, ob KI helfen könnte',
    'in Teile zerlegen und erwägen, wie KI bei einzelnen Schritten helfen könnte',
    'Aufgaben nach menschlichen Stärken und KI-Fähigkeiten verteilen')),
 'Manage 4': ('Einsatz beobachten und bewerten',
   ('Entscheidungen über KI-Einsatz sollen Verantwortung, Lernen und Fairness stützen',
    'Ergebnis mit Ziel vergleichen, nachsteuern oder selbst verbessern',
    'Prüfpunkte nach Rollen setzen, Fortschritt an Erfolgskriterien beobachten, Rollen anpassen')),
 'Shape 1': ('untersuchen, wie ein System arbeiten soll, für wen es entworfen ist und wo seine Grenzen liegen',
   ('wofür verschiedene Systeme gemacht sind',
    'Zweck, Adressatenkreis und Beschränkungen eines Werkzeugs beschreiben',
    'Stärken und Grenzen eines Werkzeugs anhand von Zweck, Adressaten, Beschränkungen und möglichen Folgen bewerten')),
 'Shape 2': ('Systeme an festgelegten Kriterien, erwarteten Ergebnissen, Testfällen und Nutzerrückmeldung bewerten',
   ('Kriterien festlegen, ob ein System eine Aufgabe erfüllt hat',
    'die Leistung eines Systems an festgelegten Kriterien und an Rückmeldungen aus menschlicher Prüfung oder Benchmark-Tests messen',
    'eigene Kriterien entwerfen, über verschiedene Eingaben und Nutzer vergleichen, Verbesserungen vorschlagen')),
 'Shape 3': ('KI-Systeme entwerfen mit Blick darauf, wie Datenquellen, Auswahl und Informationsfluss Verhalten und Ausgaben beeinflussen',
   ('Beispiele für Trainingsdaten benennen',
    'Bedeutung von Auswahl und Erhebung der Daten vergleichen, wo KI über andere entscheidet',
    'bewerten, wie Eigenschaften eines Datensatzes (Größe, Merkmale, Verzerrungen) Leistung und Wirkung eines Modells beeinflussen')),
 'Shape 4': ('Systeme für Wohlergehen und gesellschaftlichen Nutzen verbessern',
   ('erkennen, dass Systeme so entworfen oder angepasst werden können, dass sie Menschen, Gemeinschaften und Umwelt besser dienen',
    'konkrete Änderungen vorschlagen, für sich und andere',
    'Verbesserungen nach technischen Grenzen, ethischen Erwägungen und Nutzerbedürfnissen entwerfen und begründen')),
}

# The 57 measures ("In the Classroom") as German keyword phrases, condensed from
# the wording in classroom_scenarios.tsv, nothing added. Written 2026-09-19.
MEASURES = {
 ('Engage 1', 'Basic'): '„AI or Not“: Smart-Home-Geräte, soziale Netzwerke, Apps danach sortieren, ob sie KI nutzen',
 ('Engage 1', 'Intermediate'): '„for you“-Seiten sozialer Netzwerke vergleichen; reflektieren, wie und warum man von ihnen beeinflusst wird',
 ('Engage 1', 'Advanced'): 'Screenshots von Chatbots und Apps: überreden statt informieren? besprechen, ob Streak-Zähler, Figurennamen, übermäßig zustimmende Antworten auf Bindung angelegt sein könnten',
 ('Engage 2', 'Basic'): 'Redeweisen wie „KI denkt“: erkennen, welche irreführen; bessere, technisch zutreffende Beschreibungen entwickeln; Wirkung der Sprache reflektieren',
 ('Engage 2', 'Intermediate'): 'einen Mythos unter Gleichaltrigen erkennen; Plakat, Video oder Podcast, das erklärt, wie KI arbeitet',
 ('Engage 2', 'Advanced'): 'Entwurfsmerkmale vergleichen, die Systeme menschlich, freundlich, intelligent wirken lassen; Ausgaben als programmierte Vorgänge erklären; Wirkung auf Verständnis und Vertrauen reflektieren',
 ('Engage 3', 'Basic'): 'KI-Lösung einer Matheaufgabe samt Erklärung mit dem Verfahren der Lehrkraft vergleichen',
 ('Engage 3', 'Intermediate'): 'Reiseplan; KI-Restaurantempfehlungen an anderen Quellen auf Veraltetes, Falsches oder „hallucination“ prüfen; eigenes Urteil',
 ('Engage 3', 'Advanced'): 'KI-Deutungen eines historischen Ereignisses an Primär- und Sekundärquellen prüfen; begründen, welche in den Bericht kommt',
 ('Engage 4', 'Basic'): 'Film- und Serienempfehlungen für eine Buchfigur, mit Textbelegen; Vergleich mit der Art, wie KI empfiehlt',
 ('Engage 4', 'Intermediate'): 'Empfehlungen einer Musik-App mit der eigenen Liste vergleichen: verstärkt oder erweitert?',
 ('Engage 4', 'Advanced'): 'Fallstudien zu Empfehlungssystemen sozialer Netzwerke und öffentlichem Verständnis; besprechen, wie das Wahlverhalten beeinflussen könnte',
 ('Engage 5', 'Basic'): 'Geräte im Raum auflisten, die geladen und gekühlt werden; KI braucht ebenso Strom und Hardware',
 ('Engage 5', 'Intermediate'): 'Artikel, Podcast oder Video: Training großer Modelle im Vergleich zum Haushaltsverbrauch',
 ('Engage 5', 'Advanced'): 'Umweltfolgen von KI und Rechenzentren in verschiedenen Gemeinden recherchieren; Politiken und Strategien für verantwortlichen Einsatz und verantwortliche Entwicklung benennen',
 ('Engage 6', 'Basic'): 'Daten, die über eine Person erhoben werden können; was sie erfassen und was, aus der Kenntnis voneinander, fehlt',
 ('Engage 6', 'Intermediate'): 'wie und warum Gesichtserkennung je nach Gruppe verschieden arbeitet; mögliche Folgen, wo sie im Alltag Entscheidungen trifft',
 ('Engage 6', 'Advanced'): 'KI-Einfluss auf ein Ereignis (Desinformation) bewerten; wem die Entscheidungen einer Institution über KI-Einsatz nützen und wem sie schaden könnten',
 ('Engage 7', 'Basic'): 'Züge der Arbeit von Künstlern in KI-Beispielen erkennen; faire Nutzung und Folgen für die Künstler besprechen',
 ('Engage 7', 'Intermediate'): 'Fall Werbung aus dem Browserverlauf: Ersparnis gegen Privatsphäre abwägen, kurz- und langfristig',
 ('Engage 7', 'Advanced'): 'KI in der Klimadatenanalyse: Vorhersagekraft gegen Transparenz, „hallucinations“ und übersehene Unsicherheiten abwägen',
 ('Create 1', 'Basic'): 'KI-Bilder als Schauplätze aus Ideen der Mitschüler; neue Geschichten aus unerwarteten Ergebnissen',
 ('Create 1', 'Intermediate'): 'erst allein brainstormen, dann KI-Ideen vergleichen; besprechen, wie KI-Vorschläge Originalität, Zuversicht oder Entscheidungen prägen könnten',
 ('Create 1', 'Advanced'): 'eigene Debattenargumente; KI-Gegenargumente der Lehrkraft umbauen oder verwerfen',
 ('Create 2', 'Basic'): 'ein Bild zu einem Thema; erklären, wie Prompt-Elemente das Ergebnis prägten; Überraschungen; Passung zur Idee bewerten',
 ('Create 2', 'Intermediate'): 'Konzept für einen Schulclub; mehrere Leitsätze, Ideen, Bildstile mit Text- und Bildgeneratoren; vergleichen, wie verschiedene Prompts und Werkzeuge dieselbe Idee verschieden auslegen',
 ('Create 2', 'Advanced'): 'interaktives Projekt: Textgenerator für den Ablauf, Bildgenerator für den Aufbau, Code-Assistent für den Code; zu einem Prototyp zusammenführen; Rückmeldung von Mitschülern',
 ('Create 3', 'Basic'): 'Antworten auf zwei Fassungen eines Rückmelde-Prompts vergleichen; welche Merkmale (Kontext, Spezifität, Einschränkungen) die Rückmeldung genauer oder nützlicher machten',
 ('Create 3', 'Intermediate'): '3D-Modell eines geometrischen Gartens; KI-Maße mit eigenen Berechnungen prüfen; neue Gestaltungsansätze',
 ('Create 3', 'Advanced'): 'früher Entwurf gegen Endfassung mit Rückmeldung eines KI-Werkzeugs; je Änderung markieren: Werkzeug oder eigenes Denken; Reflexion über genutzte, angepasste, ignorierte Vorschläge',
 ('Create 4', 'Basic'): 'KI-Musik, die eine berühmte Künstlerin oder einen berühmten Künstler imitiert; Urheberrecht, Eigentum, Nennung besprechen',
 ('Create 4', 'Intermediate'): 'Originalarbeit gegen KI-Gedichte: was ist „original“; Schulregeln zur Nennung von KI-Einsatz',
 ('Create 4', 'Advanced'): 'Werke ganz von Menschen, ganz von KI, von Künstlern mit KI: welche Entscheidungen, wer als Künstler genannt werden sollte, was geschützt gehört, wie KI das Kunstschaffen verändern könnte',
 ('Manage 1', 'Basic'): 'nach Vorgaben der Lehrkraft Werkzeuge Aufgaben zuordnen (KI zum Zusammenfassen, Suchmaschine zur Recherche)',
 ('Manage 1', 'Intermediate'): 'zu Alltagsaufgaben in Ecken des Raums gehen („AI Only“, „AI-Supported“, „Human Only“, „Not Sure“); Wahl verteidigen, bei Überzeugung Ecke wechseln',
 ('Manage 1', 'Advanced'): 'Aufsatzschritte zerlegen; bei welchen KI unterstützen könnte und welche die eigene Stimme und das eigene Denken brauchen; Schulregeln beachten',
 ('Manage 2', 'Basic'): 'Müllsortieren: Zufall, ein Mitschüler als regelgesteuerter Roboter, Muster aus Umfragedaten; passender Ansatz je Aufgabe',
 ('Manage 2', 'Intermediate'): 'regelgesteuerte Technik (Taschenrechner, Ampel) gegen trainierte (Bilderkennung, Übersetzung); warum jeder Ansatz passt',
 ('Manage 2', 'Advanced'): 'Fälle wie Routenplanung, Inhaltsmoderation: Regeln, Lernen oder keine KI; Empfehlung begründen und in der Debatte vertreten',
 ('Manage 3', 'Basic'): 'Probleme (Wetter, einen Freund trösten, Plagiate) nach Typ einordnen; hilft KI, und ist sie nötig?',
 ('Manage 3', 'Intermediate'): 'Rechercheprojekt in Schritte zerlegen; Schritte für KI benennen; Behauptungen selbst prüfen, Verzerrung einschätzen, eigene Deutung',
 ('Manage 3', 'Advanced'): 'zwei Fassungen desselben Produkts, mit und ohne KI, in begrenzter Zeit; vorher Schritte nach KI-Fähigkeit und menschlicher Stärke verteilen; vergleichen, Rollen ändern, Wirkung erklären',
 ('Manage 4', 'Basic'): 'KI-Einsatz in Branchen (Sport, Journalismus, Musik): wo KI von Vorteil sein könnte, wo ein Mensch die aktivere Rolle übernehmen sollte',
 ('Manage 4', 'Intermediate'): 'Videos selbstfahrender Autos: wie ein Mensch anders entscheiden könnte, wann sein Urteil den Algorithmus überstimmen sollte',
 ('Manage 4', 'Advanced'): 'Kampagne im Team; KI-Botschaften und -Bilder an Zielgruppe und Zielen messen; wo KI-Inhalte irreführen oder am Ziel vorbeigehen, Rollen oder Abläufe ändern',
 ('Shape 1', 'Basic'): 'Modellkarten lesen (Arbeitsweise, Trainingsdaten, vorgesehene Nutzung, Grenzen); angemessene Nutzung besprechen',
 ('Shape 1', 'Intermediate'): 'mehrere Werkzeuge (Chatbot, Empfehlungssystem, Routen-App): Hauptaufgabe, Eingabe, wie die Ausgabe die Aufgabe erledigt',
 ('Shape 1', 'Advanced'): 'Navigations-App mit Verkehrsdaten: möglicher Zeitgewinn für einige, mehr Stau, Lärm oder Sicherheitsrisiken für bestimmte Viertel',
 ('Shape 2', 'Basic'): 'Kriterien für ein Musik-Empfehlungssystem definieren; Empfehlungen für verschiedene Nutzer vergleichen',
 ('Shape 2', 'Intermediate'): 'Strategien der Mitschüler für ein Worträtsel gegen einen Algorithmus, nach Kriterien (Effizienz, Konsistenz, Klarheit) vergleichen; Stärken, Grenzen und Abwägungen je Ansatz benennen',
 ('Shape 2', 'Advanced'): 'Vorschläge für ein KI-Werkzeug in Paaren; füreinander Modellkarten ausfüllen (Nutzer, Wirkungen, Anwendungsfälle); überarbeiten',
 ('Shape 3', 'Basic'): 'KI-Werkzeug zum Sortieren von Wertstoffen entwerfen; welche Daten sich im Internet sammeln lassen, um es zu trainieren; welche Eigenschaften der Daten am meisten zählen',
 ('Shape 3', 'Intermediate'): 'Verfahren vergleichen, Tiere nach Merkmalen zu ordnen; was geschieht mit neuen Tieren, die nicht passen',
 ('Shape 3', 'Advanced'): 'Klassen-, Jahrgangs- und Schulumfrage zum Klassentier vergleichen; wie Größe und Vielfalt der Daten das Ergebnis ändern; KI-Empfehlungen nach Trainingsdaten',
 ('Shape 4', 'Basic'): 'Alltagsprobleme in der Schule; einfache Änderungen an KI-Werkzeugen (klarere Anweisungen, altersgerechte Ausgaben, Optionen); wem sie nützen',
 ('Shape 4', 'Intermediate'): 'KI-Werkzeug, das die Nachfrage nach Bibliotheksbüchern vorhersagt: analysieren, wie Datenquellen, Kategorien und Empfehlungen bestimmen, welche Interessen vertreten sind; Änderungen planen (Nutzereingaben, Kategorien, Rückkopplungen); Zugänglichkeit für verschiedene Lernbedürfnisse',
 ('Shape 4', 'Advanced'): 'Modell für Asthma-Warnungen aus lokalen Umweltdaten entwerfen oder ändern; Daten, Vorhersage, Warnweg; mit Rückmeldung verfeinern und erklären, wie das Wohlergehen und Vertrauen der Gemeinschaft stützt',
}

# --- loading ------------------------------------------------------------------

def _read(path, n_fields):
    rows = []
    with path.open(encoding='utf-8', newline='') as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip('\n')
            if n == 1 or not line.strip():
                continue
            fields = line.split('\t')
            assert len(fields) == n_fields, f'{path.name} Zeile {n}: {len(fields)} Felder statt {n_fields}'
            rows.append((n, [x.strip() for x in fields]))
    return rows


def load_expectations():
    exp = OrderedDict()
    for n, f in _read(EXP_TSV, 9):
        komp, dom, nr, statement, basic, inter, adv, ksa, seite = f
        assert komp in COMP, f'{EXP_TSV.name} Zeile {n}: unbekannte Kompetenz {komp!r}'
        exp[komp] = dict(statement=statement, Basic=basic, Intermediate=inter,
                         Advanced=adv, ksa=ksa, seite=seite)
    assert set(exp) == set(COMP), 'learner_expectations.tsv und C nennen verschiedene Kompetenzen'
    for komp, c in COMP.items():
        a = exp[komp]['statement'].replace('\u2019', "'").strip()
        b = c['label_en'].replace('\u2019', "'").strip()
        assert a == b, (f'{komp}: der Kompetenzsatz im Generator weicht von '
                        f'{EXP_TSV.name} ab.\n  Generator : {b}\n  Endfassung: {a}')
    return exp


def load_scenarios():
    sc = OrderedDict()
    for n, f in _read(SCEN_TSV, 4):
        komp, stufe, text, seite = f
        assert komp in COMP, f'{SCEN_TSV.name} Zeile {n}: unbekannte Kompetenz {komp!r}'
        assert stufe in LEVELS, f'{SCEN_TSV.name} Zeile {n}: unbekannte Stufe {stufe!r}'
        assert (komp, stufe) not in sc, f'{SCEN_TSV.name} Zeile {n}: {komp} {stufe} doppelt'
        sc[(komp, stufe)] = dict(text=text, seite=seite)
    missing = [(k, lv) for k in COMP for lv in LEVELS if (k, lv) not in sc]
    assert not missing, f'{SCEN_TSV.name}: Szenarien fehlen: {missing}'
    assert set(MEASURES) == set(sc), 'MEASURES und classroom_scenarios.tsv decken sich nicht'
    return sc


def load_support():
    rows = []
    for n, f in _read(SUP_TSV, 7):
        teil, komp, stufe, status, wie, szen, beleg = f
        assert komp in COMP, f'{SUP_TSV.name} Zeile {n}: unbekannte Kompetenz {komp!r}'
        assert stufe in LEVELS, f'{SUP_TSV.name} Zeile {n}: unbekannte Stufe {stufe!r}'
        assert status in STATUS, f'{SUP_TSV.name} Zeile {n}: unbekannter Status {status!r}'
        if status == 'nein':
            assert not teil and not szen, f'{SUP_TSV.name} Zeile {n}: nein traegt keinen Teil und kein Szenario'
            assert wie, f'{SUP_TSV.name} Zeile {n}: nein braucht den Grund in wie_de'
        else:
            assert teil in P, f'{SUP_TSV.name} Zeile {n}: unbekannter Teil {teil!r}'
            assert wie and szen and beleg, f'{SUP_TSV.name} Zeile {n}: wie_de, szenario_de und beleg sind Pflicht'
        rows.append(dict(komp=komp, stufe=stufe, status=status, teil=teil,
                         wie=wie, szen=szen, beleg=beleg,
                         id=f'{COMP[komp]["code"]}--{stufe.lower()}--{teil or "none"}'))
    seen = {}
    for r in rows:
        key = (r['komp'], r['stufe'])
        seen.setdefault(key, set()).add(r['status'])
    for key, st in seen.items():
        assert not ('nein' in st and len(st) > 1), f'{key}: nein neben einer Unterstuetzung'
    missing = [(k, lv) for k in COMP for lv in LEVELS if (k, lv) not in seen]
    assert not missing, f'{SUP_TSV.name}: Massnahmen ohne Zeile: {missing}'
    dup = [(r['komp'], r['stufe'], r['teil']) for r in rows]
    assert len(dup) == len(set(dup)), 'eine Massnahme nennt denselben Teil zweimal'
    return rows


EXP = load_expectations()
SCEN = load_scenarios()
S = load_support()


def by_measure(komp, stufe):
    return [r for r in S if r['komp'] == komp and r['stufe'] == stufe]


def by_part(key):
    return [r for r in S if r['teil'] == key]


def part_md(key):
    n_de, _, route, kind = P[key]
    if route == 'querliegend':
        return f'{n_de} ({kind}, ohne eigenen Ort)'
    return f'{n_de} `{route}`'


def status_de(s):
    return {'ja': 'ja', 'angepasst': 'ja, angepasst', 'nein': 'nein'}[s]


# --- legend -------------------------------------------------------------------
LEGENDE_DE = [
    ('**Die Frage, die jede Zeile beantwortet.** Ob ein Teil dieser Plattform eine '
     'Maßnahme unterstützt, die das AILit-Rahmenwerk beschreibt, und wenn ja, wie, '
     'und welches Praxis-Szenario das belegt. Die Maßnahmen sind die Unterrichtsbeispiele '
     'des Rahmenwerks („In the Classroom“), eines je Kompetenz und Stufe, 57 im Ganzen; '
     'sie stehen hier im Wortlaut, mit Seite. Sie sind Vorhaben einer Lehrkraft mit '
     'ihrer Gruppe, und die Plattform wird als Werkzeug dafür beurteilt.'),
    ('**Die drei Antworten.** *ja*: die Maßnahme läuft mit diesem Teil, wie das '
     'Rahmenwerk sie beschreibt. *ja, angepasst*: der Kern der Maßnahme bleibt, ihr '
     'konkreter Gegenstand ist ersetzt (eine Musik-App durch ein Bildmodell, eine '
     'berühmte Künstlerin durch die Gruppe selbst); die Spalte *Wie* nennt den Ersatz. '
     '*nein*: kein Teil der Plattform dient der Maßnahme; die Zeile sagt, was die '
     'Maßnahme braucht und hier fehlt. Eine Maßnahme, die auf der Plattform durch eine '
     'andere Maßnahme ersetzt werden müsste, steht als *nein*.'),
    ('**Welchen Gegenstand ein Teil halten muss.** Getragen ist eine Maßnahme, wenn '
     'die Plattform den Gegenstand hält, um den die Maßnahme selbst geht. Die '
     'Vorbereitung davor und die Nachbesprechung danach liegen vor und hinter jeder '
     'Maßnahme, die eine Kursleitung durchführt, und tragen darum keine Zeile.'),
    ('**Warum hier keine Ampel steht.** Eine Schwelle, ab der eine Kompetenz als '
     'abgedeckt gälte, sieht das Rahmenwerk an keiner Stelle vor. Die Stufen sind ein '
     'Entwicklungsverlauf und ausdrücklich Material für eigene Bewertungsraster der '
     'Lehrkraft (S. 25: „Teachers and educators are encouraged to use these Learner '
     'Expectations to build their own evaluation rubrics“), Vollabdeckung erwartet es '
     'ausdrücklich nicht (S. 9: „it may not always be realistic for one educator to '
     'address every aspect in depth“), und die Unterrichtsbeispiele sollen an den Ort '
     'angepasst werden (S. 25: „should be adapted to local contexts, guidance and '
     'legislation“).'),
    ('**Was bis zum 2026-09-19 hier stand.** Die Zeilen beurteilten, ob die Plattform '
     'selbst die Handlung hervorbringt, die eine Stufe von Lernenden verlangt; Zeilen, '
     'in denen die Lehrkraft handelt, trugen „kein Stufenbezug“. Das beurteilte die '
     'Plattform als pädagogischen Akteur. Die Maßnahmen des Rahmenwerks sind '
     'Handlungen von Menschen, und ein Werkzeug wird daran gemessen, ob es sie trägt.'),
    ('**Die Namen der Stufen** sind die des Rahmenwerks und bleiben unübersetzt. '
     'Wo die Texte deutsch sprechen, meint *Grundstufe* Basic, *Mittelstufe* '
     'Intermediate und *Fortgeschrittenenstufe* Advanced.'),
]


def cell(t):
    return t.replace('|', '\\|').replace('\n', ' ')


# --- by competence ------------------------------------------------------------

def build_md():
    o = ['# Welche Maßnahmen des AILit-Rahmenwerks diese Plattform unterstützt, nach Kompetenz\n',
         f'**Quelle des Wortlauts:** {QUELLE_DE}\n',
         '**Quelltext.** Quelle ist `docs/ailit/unterstuetzung.tsv`; dort wird geändert, '
         'und `python3 devserver/scripts/build_ailit_support.py` schreibt diese Datei, '
         '`docs/AILIT_ORTE_ZUORDNUNG.md`, `docs/AILIT_ZUORDNUNGSTABELLE.md` und '
         '`devserver/my_app/knowledge/ailit_coverage.json` neu.\n']
    for line in LEGENDE_DE:
        o.append(line + '\n')
    n_sup = sum(1 for k in COMP for lv in LEVELS if by_measure(k, lv)[0]['status'] != 'nein')
    o.append(f'**Stand.** Von den 57 Maßnahmen unterstützt die Plattform {n_sup}, '
             f'{57 - n_sup} nicht. Die Zeilen unten sagen je Maßnahme, welche.\n')
    for komp, c in COMP.items():
        e = EXP[komp]
        o.append(f"\n## {komp} — {c['kurz_de']}\n")
        o.append(f"*Kompetenz (S. {e['seite']}): „{e['statement']}“*  \n"
                 f"*Deutsch: {c['label_de']}*\n")
        for lv in LEVELS:
            rows = by_measure(komp, lv)
            sc = SCEN[(komp, lv)]
            o.append(f'\n### {komp} {lv}\n')
            o.append(f"*Learner Expectation (S. {e['seite']}): „{e[lv]}“*  \n"
                     f"*In the Classroom (S. {sc['seite']}): „{sc['text']}“*\n")
            if rows[0]['status'] == 'nein':
                o.append(f"**Unterstützt: nein.** {rows[0]['wie']}\n")
                continue
            for r in rows:
                o.append(f"**{part_md(r['teil'])} — {status_de(r['status'])}.** {r['wie']}\n")
                o.append(f"*Praxis-Szenario.* {r['szen']}  \n"
                         f"<sub>Beleg: `{r['beleg']}`</sub>\n")
    return '\n'.join(o) + '\n'


# --- by part ------------------------------------------------------------------

def build_places_md():
    o = ['# Welche Maßnahmen des AILit-Rahmenwerks diese Plattform unterstützt, nach Teil der Plattform\n',
         f'**Quelle des Wortlauts:** {QUELLE_DE}\n',
         '**Quelltext.** Dieselbe Quelle wie `docs/OECD_AILIT_ABDECKUNG.md`: '
         '`docs/ailit/unterstuetzung.tsv`, gebaut von '
         '`devserver/scripts/build_ailit_support.py`. Hier nach Teil geordnet.\n']
    for line in LEGENDE_DE:
        o.append(line + '\n')
    for kind, titel in KINDS:
        keys = [k for k, v in P.items() if v[3] == kind]
        o.append(f'\n## {titel}\n')
        o.append('**Übersicht.** ' + ' · '.join(
            f'{P[k][0]} {len(by_part(k))}' for k in keys) + '\n')
        for key in keys:
            rows = by_part(key)
            if not rows:
                continue
            o.append(f'\n### {part_md(key)}\n')
            wort = 'Eine Maßnahme' if len(rows) == 1 else f'{len(rows)} Maßnahmen'
            o.append(f'*{wort}.*\n')
            for r in rows:
                e = EXP[r['komp']]
                sc = SCEN[(r['komp'], r['stufe'])]
                o.append(f"#### {r['komp']} {r['stufe']} — {COMP[r['komp']]['kurz_de']} · "
                         f"{status_de(r['status'])}\n")
                o.append(f"*Learner Expectation (S. {e['seite']}): „{e[r['stufe']]}“*  \n"
                         f"*In the Classroom (S. {sc['seite']}): „{sc['text']}“*\n")
                o.append(f"{r['wie']}\n")
                o.append(f"*Praxis-Szenario.* {r['szen']}  \n"
                         f"<sub>Beleg: `{r['beleg']}`</sub>\n")
    empty = [k for k in P if not by_part(k)]
    o.append('\n## Teile ohne Maßnahme\n')
    o.append('Keine der 57 Maßnahmen des Rahmenwerks nennt etwas, das diese Teile '
             'tragen; was sie tun, steht in ihrer Anrede und im Katalog von Help.\n')
    for k in empty:
        o.append(f'- {part_md(k)}')
    return '\n'.join(o) + '\n'


# --- the plain table ----------------------------------------------------------

def build_table():
    """The plain table starts from the platform, as the table of 2026-09-02 did
    and as Help reads it: one row per part (mode, instrument, cross-cutting
    function, in the order of P) and measure the part supports, the part named
    once. The measures no part carries close the table under their own
    heading; the parts without a measure are named in one line."""
    head = ['Art', 'Teil', 'Route', 'Kompetenz', 'Kompetenz im Klartext', 'Stufe',
            'Erwartung (Stichwort)', 'OECD-Maßnahme (Stichwort)', 'Unterstützt', 'Wie',
            'Praxis-Szenario', 'Beleg']
    order = {m: i for i, m in enumerate((k, lv) for k in COMP for lv in LEVELS)}

    def keywords(r):
        i = LEVELS.index(r['stufe'])
        return [r['komp'], PHRASES[r['komp']][0], r['stufe'], PHRASES[r['komp']][1][i],
                MEASURES[(r['komp'], r['stufe'])]]

    groups = [(k, sorted(by_part(k), key=lambda r: order[(r['komp'], r['stufe'])])) for k in P]
    rows = []
    for key, part_rows in groups:
        n_de, _, route, kind = P[key]
        for r in part_rows:
            rows.append([kind, n_de, '' if route == 'querliegend' else route] + keywords(r)
                        + [status_de(r['status']), r['wie'], r['szen'], r['beleg']])
    unsupported = []
    for komp in COMP:
        for lv in LEVELS:
            r = by_measure(komp, lv)[0]
            if r['status'] == 'nein':
                unsupported.append(['', '', ''] + keywords(r) + ['nein', r['wie'], '', ''])
    n_parts = sum(1 for _, part_rows in groups if part_rows)
    empty = [part_md(k) for k, part_rows in groups if not part_rows]
    md = ['# AILit-Zuordnungstabelle: Teil der Plattform × OECD-Maßnahme, im Klartext\n',
          f'{len(rows)} Zuordnungen an {n_parts} Teilen der Plattform; {len(unsupported)} der '
          f'57 Maßnahmen trägt kein Teil (am Ende). Eine Zeile je Teil und Maßnahme, die er '
          'unterstützt, in der Ordnung der Plattform: die Modi, die Instrumente des Latent Lab, '
          'die querliegenden Funktionen. Die Stichworte fassen den Wortlaut zusammen, nichts '
          'ist hinzugefügt; der Wortlaut jeder Erwartung und Maßnahme steht je Teil in '
          '`docs/AILIT_ORTE_ZUORDNUNG.md` und je Kompetenz in `docs/OECD_AILIT_ABDECKUNG.md`. '
          '*ja, angepasst* heißt: der Kern der Maßnahme bleibt, ihr Gegenstand ist ersetzt, '
          'und die Spalte *Wie* nennt den Ersatz.\n',
          f'**Quelle des Wortlauts:** {QUELLE_DE}\n',
          'Erzeugt von `devserver/scripts/build_ailit_support.py` aus '
          '`docs/ailit/unterstuetzung.tsv`; dort wird geändert, nicht hier. Daneben liegt '
          'dieselbe Tabelle als `AILIT_ZUORDNUNGSTABELLE.tsv`, und Help liest sie je Seite '
          'aus `devserver/my_app/knowledge/ailit_coverage.json`.\n']
    for kind, titel in KINDS:
        md.append(f'**{titel}.** ' + ' · '.join(
            f'{P[k][0]} {len(part_rows)}' for k, part_rows in groups if P[k][3] == kind) + '\n')
    md.append('Ohne Maßnahme: ' + ', '.join(empty) + '.\n')
    md += ['| Teil | OECD-Kompetenz | Stufe: Erwartung | OECD-Maßnahme | Unterstützt | Wie | Praxis-Szenario |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for key, part_rows in groups:
        n_de, _, route, kind = P[key]
        first = (f'**{n_de}** ({kind}, ohne eigenen Ort)' if route == 'querliegend'
                 else f'**{n_de}** `{route}`')
        for j, r in enumerate(part_rows):
            komp, kphr, lv, lphr, mphr = keywords(r)
            md.append(f'| {first if j == 0 else ""} | **{komp}** {cell(kphr)} | '
                      f'**{lv}** {cell(lphr)} | {cell(mphr)} | {status_de(r["status"])} | '
                      f'{cell(r["wie"])} | {cell(r["szen"])} |')
    md += ['\n## Maßnahmen, die kein Teil trägt\n',
           '| OECD-Kompetenz | Stufe: Erwartung | OECD-Maßnahme | Grund |',
           '| --- | --- | --- | --- |']
    for u in unsupported:
        _, _, _, komp, kphr, lv, lphr, mphr, _, grund, _, _ = u
        md.append(f'| **{komp}** {cell(kphr)} | **{lv}** {cell(lphr)} | {cell(mphr)} | {cell(grund)} |')
    return '\n'.join(md) + '\n', head, rows + unsupported


# --- JSON for Help ------------------------------------------------------------

def build_json():
    def place(k):
        n_de, n_en, route, kind = P[k]
        return {'key': k, 'name': n_en, 'name_de': n_de, 'route': route, 'kind': kind,
                'views': VIEWS.get(k, []), 'aliases': ALIASES.get(k, [])}

    def goal(r):
        # What Help renders per measure (platform_items.goals): the competence,
        # the level with its verbatim Learner Expectation and page, the verbatim
        # classroom scenario with its page, then how this part carries the
        # measure and the practical scenario (German).
        c = COMP[r['komp']]
        e = EXP[r['komp']]
        sc = SCEN[(r['komp'], r['stufe'])]
        return {'competence': f"{r['komp']} \u2014 {c['label_en']}",
                'level': r['stufe'], 'page': e['seite'], 'expectation': e[r['stufe']],
                'classroom': sc['text'], 'classroom_page': sc['seite'],
                'status': r['status'], 'how_de': r['wie'], 'practice_de': r['szen']}

    by_route = OrderedDict()
    by_part = OrderedDict()
    for r in S:
        if r['status'] == 'nein':
            continue
        route = P[r['teil']][2]
        if route.startswith('/'):
            by_route.setdefault(route, []).append(goal(r))
        else:
            # The cross-cutting functions have no route; Help reaches their
            # measures by the part's key or name (platform_items.find_place).
            by_part.setdefault(r['teil'], []).append(goal(r))
    comps = []
    for komp, c in COMP.items():
        e = EXP[komp]
        comps.append({
            'code': c['code'], 'label': komp, 'domain': c['domain'], 'number': c['n'],
            'competence': c['label_en'], 'competence_de': c['label_de'],
            'key_de': c['kurz_de'], 'page': e['seite'],
            'levels': {lv: {'expectation': e[lv], 'page': e['seite'],
                            'classroom': SCEN[(komp, lv)]['text'],
                            'classroom_page': SCEN[(komp, lv)]['seite'],
                            'supported': by_measure(komp, lv)[0]['status'] != 'nein'}
                       for lv in LEVELS},
        })
    return {
        '_source': [
            f'Framework: {QUELLE_EN}. 19 competences in four domains, 57 Learner Expectations, 57 "In the Classroom" scenarios.',
            'Verbatim competence statements and Learner Expectations: docs/ailit/learner_expectations.tsv; verbatim classroom scenarios: docs/ailit/classroom_scenarios.tsv, both with page numbers. Provenance and reading rule: docs/ailit/QUELLE.md.',
            'Support: docs/ailit/unterstuetzung.tsv, one row per classroom scenario and part of the platform that supports it; how_de and practice_de are German.',
            'by_route: route -> the supported measures of that page as Help renders them (competence, level, page, expectation, classroom, classroom_page, status, how_de, practice_de); by_part: the same for the cross-cutting functions, keyed by part; places carry the view names (views) and the earlier addresses (aliases) of the pages the catalogue platform_items.json has no entry for.',
            'Built by devserver/scripts/build_ailit_support.py together with docs/OECD_AILIT_ABDECKUNG.md, docs/AILIT_ORTE_ZUORDNUNG.md and docs/AILIT_ZUORDNUNGSTABELLE.md.',
        ],
        'frame': {
            'question': ('Whether a part of this platform supports a measure the AILit framework '
                         'describes (its "In the Classroom" scenario for a competence and level), '
                         'how, and which practical scenario shows it. The measures are human-led '
                         'activities; the platform is judged as a tool for them.'),
            'status': {'ja': 'the measure runs with this part as described',
                       'angepasst': "the measure's core keeps, its concrete object is replaced; how_de names the replacement",
                       'nein': 'no part of the platform serves the measure; why_de says what it needs'},
            'no_threshold': ('The framework sets no threshold at which a competence would count as '
                             'covered (p. 25, p. 9) and says its classroom scenarios should be '
                             'adapted to local contexts (p. 25). This file carries no coverage '
                             'verdict and no tally.'),
        },
        'competences': comps,
        'places': [place(k) for k in P],
        # route -> the measures a page supports, ready for Help: read by
        # build_platform_items.py into the catalogue and by
        # platform_items.py for the pages the catalogue has no entry for.
        'by_route': by_route,
        # part key -> the measures of a cross-cutting function (kind Funktion,
        # no route of its own), for lookup_place by name.
        'by_part': by_part,
        'support': [
            {'id': r['id'], 'competence': COMP[r['komp']]['code'], 'label': r['komp'],
             'level': r['stufe'], 'status': r['status'], 'place': place(r['teil']),
             'how_de': r['wie'], 'practice_de': r['szen'], 'evidence': r['beleg']}
            for r in S if r['status'] != 'nein'],
        'unsupported': [
            {'competence': COMP[r['komp']]['code'], 'label': r['komp'],
             'level': r['stufe'], 'why_de': r['wie']}
            for r in S if r['status'] == 'nein'],
    }


# --- SQLite -------------------------------------------------------------------

def build_sqlite(path):
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute('CREATE TABLE kompetenz (label TEXT PRIMARY KEY, code TEXT, domain TEXT, n INTEGER, '
                'kurz_de TEXT, label_de TEXT, statement_en TEXT, seite TEXT)')
    cur.execute('CREATE TABLE stufe (label TEXT, stufe TEXT, expectation_en TEXT, classroom_en TEXT, '
                'seite TEXT, erwartung_stichwort TEXT, massnahme_stichwort TEXT, '
                'PRIMARY KEY (label, stufe))')
    cur.execute('CREATE TABLE teil (key TEXT PRIMARY KEY, name_de TEXT, name_en TEXT, route TEXT, art TEXT)')
    cur.execute('CREATE TABLE unterstuetzung (id TEXT PRIMARY KEY, label TEXT, stufe TEXT, status TEXT, '
                'teil TEXT, wie_de TEXT, szenario_de TEXT, beleg TEXT)')
    for komp, c in COMP.items():
        e = EXP[komp]
        cur.execute('INSERT INTO kompetenz VALUES (?,?,?,?,?,?,?,?)',
                    (komp, c['code'], c['domain'], c['n'], c['kurz_de'], c['label_de'],
                     e['statement'], e['seite']))
        for i, lv in enumerate(LEVELS):
            cur.execute('INSERT INTO stufe VALUES (?,?,?,?,?,?,?)',
                        (komp, lv, e[lv], SCEN[(komp, lv)]['text'], e['seite'],
                         PHRASES[komp][1][i], MEASURES[(komp, lv)]))
    for k, (n_de, n_en, route, kind) in P.items():
        cur.execute('INSERT INTO teil VALUES (?,?,?,?,?)', (k, n_de, n_en, route, kind))
    for r in S:
        cur.execute('INSERT INTO unterstuetzung VALUES (?,?,?,?,?,?,?,?)',
                    (r['id'], r['komp'], r['stufe'], r['status'], r['teil'] or None,
                     r['wie'], r['szen'] or None, r['beleg'] or None))
    con.commit()
    con.close()


def main():
    OUT_MD.write_text(build_md(), encoding='utf-8')
    OUT_PLACES.write_text(build_places_md(), encoding='utf-8')
    table_md, head, rows = build_table()
    OUT_TABLE_MD.write_text(table_md, encoding='utf-8')
    with OUT_TABLE_TSV.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(head)
        w.writerows(rows)
    OUT_JSON.write_text(json.dumps(build_json(), ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    build_sqlite(OUT_SQLITE)
    for p in (OUT_MD, OUT_PLACES, OUT_TABLE_MD, OUT_TABLE_TSV, OUT_JSON):
        print(f'{p.relative_to(ROOT)}: {p.stat().st_size} B')
    print(f'{OUT_SQLITE.relative_to(ROOT)}: {OUT_SQLITE.stat().st_size} B (gitignoriert)')
    n = {s: sum(1 for r in S if r['status'] == s) for s in STATUS}
    measures_sup = sum(1 for k in COMP for lv in LEVELS if by_measure(k, lv)[0]['status'] != 'nein')
    parts = sorted({r['teil'] for r in S if r['teil']})
    print(f'{len(S)} Zeilen: ja {n["ja"]}, angepasst {n["angepasst"]}, nein {n["nein"]}. '
          f'{measures_sup} von 57 Massnahmen unterstuetzt, ueber {len(parts)} Teile; '
          f'{len(P) - len(parts)} Teile ohne Massnahme.')


if __name__ == '__main__':
    main()
