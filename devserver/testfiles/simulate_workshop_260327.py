#!/usr/bin/env python3
"""
Workshop Load Replay — 2026-03-27

Replays the 53 Stage-4 generations from the workshop (youth safety level)
with the original timing pattern:
  Phase 1 (15:17-15:39): Mixed sd35_large + qwen_img2img (Bockwurst + Drahtpflanze exercises)
  Phase 2 (16:17-17:40): Multi-config creative session (flux2 persona, qwen_img2img,
                          qwen_2511_multi, hunyuan3d_text_to_3d, wan22_i2v_video)

Devices: 7 generating (+ 2 persona/browsing-only)
Safety level: youth throughout.

Extracted from: Teilprotokoll 27 3 2026 backend.txt + RECORDER exports
Prompts are the ORIGINAL user inputs extracted from RECORDER 001_input.txt / 01_input.txt files,
and for persona-generated prompts (flux2) from 01_generation_prompt.txt.

Usage:
    python simulate_workshop_260327.py [--port 17802] [--dry-run] [--max-gap 15]

    --port PORT       Backend port (default: 17802 = development)
    --dry-run         Print timing without sending requests
    --no-image        Skip img2img/i2v (use sd35_large fallback)
    --max-gap SECONDS Cap idle gaps (default: 15s). Queue drains at every capped pause.

HOW THIS SCRIPT WAS CREATED (for future sessions creating similar scripts):
    1. Parse the backend log for [STAGE4-GEN] lines to get timestamps + output_configs:
       grep "[STAGE4-GEN] Executing generation with config" backend.txt
    2. Compute offsets from first timestamp (15:17:25.878)
    3. Extract ORIGINAL prompts from RECORDER export files:
       - For passthrough configs (qwen_img2img, wan22_i2v_video, qwen_2511_multi):
         Use 01_input.txt from the RECORDER export (= original user input)
       - For intercepted configs (sd35_large):
         Use 001_input.txt from prompting_process (= original German input before interception)
       - For persona-generated configs (flux2):
         Use 01_generation_prompt.txt (persona generated the English prompt)
       - For hunyuan3d_text_to_3d: Use 01_input.txt (original user input)
    4. flux2 is a ComfyUI backend config; its prompts are English because they come
       from Trashy persona mode (not user-typed German)
    5. hunyuan3d_text_to_3d has backend_type=hunyuan3d (GPU service)
    6. 7 generating devices, clusters checked (no more than 4 concurrent)
    7. qwen_img2img and wan22_i2v_video need input_image
    8. qwen_2511_multi needs input_image1/2/3
"""

import argparse
import asyncio
import aiohttp
import os
import time
import sys
from dataclasses import dataclass
from typing import Optional

# Force line-buffered output (critical when stdout is redirected to a file)
import functools
print = functools.partial(print, flush=True)  # type: ignore[assignment]


# --- Workshop replay data (extracted from backend log 2026-03-27) ---
# Format: (seconds_offset_from_start, output_config, original_prompt)
# Offset 0 = 15:17:25.878 (first Stage 4 generation)
# 53 entries = all Stage 4 requests during workshop
# Prompts are ORIGINAL user inputs from RECORDER exports (not synthetic).
#
# Config distribution:
#   qwen_img2img:        36 (ComfyUI) — needs input_image
#   qwen_2511_multi:      7 (ComfyUI) — needs input_image1/2/3
#   flux2:                3 (ComfyUI) — persona-generated English prompts
#   wan22_i2v_video:      3 (ComfyUI) — needs input_image (Image-to-Video!)
#   sd35_large:           2 (GPU Service/Diffusers) — intercepted, original German
#   hunyuan3d_text_to_3d: 2 (GPU Service/Hunyuan3D)
#
# Two-phase pattern:
#   Phase 1 (15:17-15:39): sd35_large + qwen_img2img — Bockwurst + Drahtpflanze
#   ~38min pause (15:39-16:17)
#   Phase 2 (16:17-17:40): Multi-config creative session

WORKSHOP_REQUESTS = [
    # === Phase 1: Bockwurst + Drahtpflanze exercises (15:17-15:39) ===
    (       0.0, "sd35_large", "Bockwurst glas, indem ein Kampffisch schwimmt"),
    (      94.0, "qwen_img2img", "der fisch soll mit den Würstchen im Wurstglas schwimmen"),
    (     470.7, "qwen_img2img", "mach aus dem Fisch einen eleganten Kampffisch"),
    (    1095.1, "qwen_img2img", "Gestalte hinter der drahtpflanze eine Landschaft"),
    (    1181.6, "qwen_img2img", "Lasse das Originalbilder. Auf der weißen Fläche erscheint eine Malerei einer Landschaft"),
    (    1304.5, "qwen_img2img", "Lasse das Originalbild, das Objekt bleibt genau da wo es ist. Auf der weißen Fläche im Hintergrund erscheint eine Malerei einer Landschaft"),

    # === ~38min PAUSE (15:39 - 16:17) ===

    # === Phase 2: Multi-config creative session (16:17-17:40) ===

    # --- Persona/flux2 shadow projections (16:17-16:20) ---
    (    3633.3, "flux2", "Shadow projection on white wall, high contrast black and white, silhouette of a human hand holding a tangled wire ball that resembles a cloud, next to it angular bent wire casting shadow that looks like lightning bolts, overhead projector aesthetic, sharp light edges fading into soft penumbra, surreal scale, the hand enormous, the cloud dense and dark, lightning jagged thin lines, minimal background, raw projected light quality, slightly out of focus at edges, art photography aesthetic"),
    (    3714.4, "flux2", "Shadow projection on white wall, high contrast black and white, elegant hand silhouette reaching down from above holding a tangled wire cloud shape delicately between two fingers, long sharp fingernails visible in shadow, angular bent wire beside it casting jagged lightning bolt shadows, overhead projector light aesthetic, sharp black shadows on bright white surface, surreal scale, the hand graceful and elongated, minimal composition, raw projected light quality with soft penumbra at edges, art photography"),
    (    3803.2, "flux2", "Shadow projection on white wall, high contrast black and white, elegant hand silhouette reaching down from top of frame holding tangled wire ball between two fingers with long sharp fingernails, beside it a thin irregular jagged bent wire casting an asymmetric crackling shadow resembling a lightning crack, NOT a lightning bolt symbol, organic imperfect angular wire shadow like a fracture or fissure, overhead projector light source from below, sharp center shadows dissolving into soft penumbra, raw analog light projection aesthetic, minimal composition, art photography, no illustration, no graphic symbols"),

    # --- qwen_img2img city/shadow exercises (16:23-16:34) ---
    (    3982.9, "qwen_img2img", "Mach das als ein stadt"),
    (    4158.8, "qwen_img2img", "Das soll ein stadt sein"),
    (    4189.6, "qwen_img2img", "Mach aus dem schattenbild eine pixellandschaft, welche Löcher hat und wo nur zwei Farben verwendet werden"),
    (    4199.8, "qwen_img2img", "Mach aus dem schattenbild eine pixellandschaft, welche Löcher hat und wo nur zwei Farben verwendet werden"),
    (    4339.0, "qwen_img2img", "Verwandle den Schwarzen Umriss in eine Blume aber behalte die Form bei. \n\nSetzte die Blume dann auf eine einsame Wiese"),
    (    4343.1, "qwen_img2img", "Verwandle den Schwarzen Umriss in eine Blume aber behalte die Form bei. \n\nSetzte die Blume dann auf eine einsame Wiese"),
    (    4440.7, "qwen_img2img", "Erstelle eine detaillierte Beschreibung einer fiktiven Stadt. Die Stadt soll lebendig und glaubwürdig wirken. Beschreibe:\nden Aufbau der Stadt (Zentrum, Viertel, Infrastruktur)\nArchitektur und typische Gebäude\ndas Leben der Bewohner (Kultur, Alltag, Atmosphäre)\nbesondere Orte oder Sehenswürdigkeiten\ndie Stimmung der Stadt (z. B. futuristisch, historisch, dystopisch oder idyllisch)"),
    (    4479.5, "qwen_2511_multi", "Verwende die Konturen des ersten Bild und das Prinzip der Landschaft aus dem zweiten Bild. Mache es etwas abstrakt und verwende nur blau und orange"),
    (    4519.5, "qwen_img2img", "Erstelle eine detaillierte Beschreibung einer fiktiven Stadt. Die Stadt soll lebendig und glaubwürdig wirken. Beschreibe:\nden Aufbau der Stadt (Zentrum, Viertel, Infrastruktur)\nArchitektur und typische Gebäude\ndas Leben der Bewohner (Kultur, Alltag, Atmosphäre)\nbesondere Orte oder Sehenswürdigkeiten\ndie Stimmung der Stadt (z. B. futuristisch, historisch, dystopisch oder idyllisch) es solll aus den blatt sein"),
    (    4604.6, "qwen_img2img", "Erstelle eine detaillierte Beschreibung einer fiktiven Stadt. Die Stadt soll lebendig und glaubwürdig wirken. Beschreibe:\nden Aufbau der Stadt (Zentrum, Viertel, Infrastruktur)\nArchitektur und typische Gebäude\ndas Leben der Bewohner (Kultur, Alltag, Atmosphäre)\nbesondere Orte oder Sehenswürdigkeiten\ndie Stimmung der Stadt (z. B. futuristisch, historisch, dystopisch oder idyllisch) es solll aus den blatt sein in den image das ich dir gegeben have"),

    # --- Blume + Wiese iterations (16:36-16:45) ---
    (    4772.5, "qwen_img2img", "Verwandle den schwarzen Umriss in eine Blume aber behalte die Form des Umrisses\n\nSetzte die Blume dann auf eine einsame Wiese"),
    (    4817.6, "qwen_img2img", "Fahhhhhhhhhhh!"),
    (    4852.4, "qwen_img2img", "Mache diesen Umriss der Blume farbig"),
    (    4911.4, "hunyuan3d_text_to_3d", "Fahhhhhhhhhhh!"),
    (    4967.2, "qwen_img2img", "Mache diesen Umriss der Blume farbig und mach den Hintergrund eine grüne Wiese"),
    (    4998.6, "qwen_2511_multi", "Verwende nur Orange und Blau und verwende das Prinzip des dritten Bildes und den Umriss des ersten Bildes und die Landschaft des zweiten Bildes"),
    (    5009.6, "hunyuan3d_text_to_3d", "Fahhhhhhhhhhh!"),
    (    5159.3, "qwen_img2img", "Mache diesen Umriss der Blume farbig und mach den Hintergrund eine grüne Wiese\n\nDie Wiese soll realistisch sein aber die Blume nicht"),
    (    5265.4, "qwen_img2img", "Mache diesen Umriss der Blume farbig und mach den Hintergrund eine grüne Wiese\n\nDie Wiese soll realistisch sein aber die Blume soll ein Umriss bleiben"),

    # --- Multi-image + landscape iterations (16:50-16:58) ---
    (    5607.1, "qwen_2511_multi", "Verwende die Linien in Bild eins, vor allem die orangenen Linien und mach es so, dass es etwas verschwommen wirkt, wie ein 3D bild ohne 3D Brille. Verwende nur Orange und Blau. Verwende kein grün. Verwende den Malstil von Bild zwei"),
    (    5660.1, "qwen_img2img", "Mach das als \nplanze"),
    (    5731.7, "qwen_2511_multi", "Verwende die Linien in Bild eins, vor allem die orangenen Linien und mach es so, dass es etwas verschwommen wirkt, wie ein 3D bild ohne 3D Brille. Verwende nur Orange und Blau. Verwende kein grün. Verwende den Malstil von Bild zwei. Mache die Bäume verdorrt und nur braun"),
    (    5869.4, "qwen_2511_multi", "Verwende die Linien in Bild eins, vor allem die orangenen Linien und mach es so, dass es etwas verschwommen wirkt, wie ein 3D bild ohne 3D Brille. Verwende nur Orange und Blau. Verwende den Malstil von Bild zwei. Mache die Bäume verdorrt und nur braun"),
    (    5918.0, "qwen_img2img", "Füge einen Hasen hinzu"),
    (    5961.8, "qwen_2511_multi", "Verwende die Linien in Bild eins, vor allem die orangenen Linien und mach es so, dass es etwas verschwommen wirkt, wie ein 3D bild ohne 3D Brille. Verwende nur Orange und Blau. Verwende den Malstil von Bild zwei. Mache die Bäume verdorrt und ganz braun ohne grün"),
    (    6054.8, "sd35_large", "Ein fest in berlin"),
    (    6086.5, "qwen_img2img", "Füge einen Hasen ganz hinten auf die Wiese hinzu"),

    # --- Wüste + internationaler Block (17:01-17:10) ---
    (    6248.6, "qwen_img2img", "Verwandle es in ein Landschaftsgemälde einer Wüste und verwende nur blau und orange"),
    (    6295.5, "qwen_img2img", "In diesem Bild wird die Szenerie in eine detaillierte Landschaftsdarstellung verwandelt. Die Umgebung zeichnet sich durch eine präzise Wiedergabe der vorhandenen Architektur und der natürlichen Elemente aus. Gebäude weisen spezifische Oberflächenstrukturen wie rauen Verputz, Ziegelmauerwerk oder glatte Glasfronten auf, die das Tageslicht diffus reflektieren. Die Vegetation im Bild wird mit botanischer Genauigkeit dargestellt, wobei die Textur der Blätter und die Beschaffenheit der Baumrinde deutlich erkennbar sind. Der Boden zeigt reale Materialien wie Kopfsteinpflaster, Asphalt mit feinen Rissen oder natürlichen Erdboden mit vereinzelten Kieselsteinen. Die Lichtverhältnisse im Bild orientieren sich an einem natürlichen Sonnenstand, der klare Schatten wirft und die dreidimensionale Form aller Objekte betont. Farbtöne sind gesättigt, bleiben aber innerhalb eines natürlichen Spektrums, um eine sachliche und räumlich greifbare Atmosphäre zu schaffen. Alle kulturellen Elemente werden als funktionale Bestandteile des öffentlichen oder privaten Raums ohne Idealisierung abgebildet."),
    (    6446.2, "qwen_img2img", "Make a plant out this image.It should be\u2026\n=It should be a Flower\n=It should be Green \n=It should be real\n=There should be a bee fling over the flower\n=behind the flower should be a rabbit \n=the backround should be a blue sky with the sun and the clouds\n=in the corner there should be the text in cursive:Frohe Ostern\n=In a another corner there should be a a Easter egg with bright colours\n=The land must have grass\n=it should look realistic"),
    (    6483.5, "qwen_img2img", "Ninu aworan yii, a ri \u1ecdk\u1ecd ay\u1ecdk\u1eb9l\u1eb9 akero kekere kan ti o duro si egbe titi ni ilu nla kan ni Naijiria. Ara \u1ecdk\u1ecd naa j\u1eb9 aw\u1ecd ofee ti o ni ila dudu ni \u1eb9gb\u1eb9. Aw\u1ecdn ero joko si inu \u1ecdk\u1ecd naa, w\u1ecdn n duro de igba ti \u1ecdk\u1ecd yoo kun ki w\u1ecdn to gbera. Ohun ti o \u1e63e pataki jul\u1ecd ninu aworan yii ni a\u1e63\u1ecd ti aw\u1ecdn obinrin ti w\u1ecdn duro l\u1eb9gb\u1eb9\u1eb9 \u1ecdk\u1ecd naa w\u1ecd. W\u1ecdn w\u1ecd a\u1e63\u1ecd adir\u1eb9 elelo bulu ti o ni aw\u1ecdn ap\u1eb9r\u1eb9 ori\u1e63iri\u1e63i ti a fi ar\u00f3 \u1e63e. Aw\u1ecdn ap\u1eb9r\u1eb9 inu a\u1e63\u1ecd naa j\u1eb9 eyi ti a fi \u1ecdna didi tabi rir\u1eb9 \u1e63e, ti o fi han bi i\u1e63\u1eb9 \u1ecdw\u1ecd aw\u1ecdn obinrin Yoruba \u1e63e ri. Ina oorun n tan si ara \u1ecdk\u1ecd ati a\u1e63\u1ecd aw\u1ecdn eniyan naa, eyi ti o n j\u1eb9 ki aw\u1ecdn aw\u1ecd bulu inu adir\u1eb9 naa t\u00e0n g\u1eb9ger\u1eb9. Ayika naa kun fun i\u1e63\u1eb9 \u1e63i\u1e63e ojooj\u00fam\u1ecd nibiti aw\u1ecdn eniyan ti n l\u1ecd si ibi i\u1e63\u1eb9 w\u1ecdn."),
    (    6534.8, "qwen_2511_multi", "Verwende die Linien als Kontur und behalte den Stil und die Farben aus Bild zwei bei. Verwende keine Pflanzen"),
    (    6583.3, "qwen_img2img", "In diesem Bild verwandelt sich die Umgebung in eine weitläufige Landschaft, die durch klare, geographische Merkmale besticht. Der Vordergrund der Szenerie ist geprägt von mineralischen Texturen und einer Bodenbeschaffenheit, die an trockene, sandige Ebenen erinnert. Im Mittelpunkt stehen architektonische Strukturen, die sich durch ihre funktionale Bauweise und die Verwendung lokaler Materialien auszeichnen. Die Beleuchtung in diesem Bild ist direkt und erzeugt scharfe Schattenkanten, was auf einen hohen Sonnenstand hindeutet. Im Hintergrund erstrecken sich Hügelketten mit spärlicher Vegetation, deren Farbspektrum von Ocker bis zu tiefen Erdtönen reicht. Die Atmosphäre wirkt ruhig und weitläufig, wobei die räumliche Tiefe durch die klare Trennung von Vorder- und Hintergrund sowie die natürliche Staffelung der Geländestufen betont wird. Sämtliche Oberflächen im Bild zeigen eine matte Beschaffenheit, die das einfallende Tageslicht weich streut."),
    (    6664.3, "qwen_img2img", "Make a plant out this image.It should be\u2026\n=It should be a Flower\n=It should be Green \n=It should be real\n=There should be a bee fling over the flower\n=behind the flower should be a rabbit \n=the backround should be a blue sky with the sun and the clouds\n=in the corner there should be the text in cursive:Frohe Ostern\n=In a another corner there should be a a Easter egg with bright colours\n=The land must have grass\n=it should look realistic\n=it should look like the form like in image"),

    # --- Late-session: landscape + video iterations (17:09-17:40) ---
    (    6698.8, "qwen_img2img", "In diesem Bild wird die Szenerie in eine detaillierte Landschaftsdarstellung übertragen. Der Fokus liegt auf der präzisen Wiedergabe von Oberflächenstrukturen und der räumlichen Anordnung der Elemente. Die Vegetation in diesem Bild zeigt spezifische botanische Merkmale, wobei die Blätter eine matte Textur und natürliche Grüntöne aufweisen. Die Architektur wird durch klare Linien und die Materialbeschaffenheit von Stein oder Holz definiert, ohne dabei dekorative Übertreibungen zu nutzen. Das Licht in diesem Bild fällt gleichmäßig auf die Oberflächen und betont die physische Präsenz der Objekte durch weiche Schattenwürfe. Die Komposition folgt einer realistischen Perspektive, die den Blick des Betrachters durch den Raum führt und dabei die Umgebung in einem sachlichen, dokumentarischen Stil festhält. Jedes Detail, von der Bodenbeschaffenheit bis hin zu den baulichen Strukturen, wird als funktionaler Bestandteil einer bewohnten oder natürlichen Umgebung dargestellt."),
    (    6773.8, "wan22_i2v_video", "Make a plant out this image.It should be\u2026\n=It should be a Flower.Use the image\n=It should be Green \n=It should be real\n=There should be a bee fling over the flower\n=behind the flower should be a rabbit \n=the backround should be a blue sky with the sun and the clouds\n=in the corner there should be the text in cursive:Frohe Ostern\n=In a another corner there should be a a Easter egg with bright colours\n=The land must have grass\n=it should look photorealistic\n=it should look like the form like in image"),
    (    6776.1, "qwen_img2img", "In diesem Bild wird die Szenerie in eine detaillierte Landschaftsdarstellung verwandelt. Der Fokus liegt auf der präzisen Wiedergabe von Oberflächentexturen und der räumlichen Anordnung der Elemente. Die Architektur im Bild zeigt klare Strukturen aus regionaltypischen Baumaterialien wie gebranntem Lehm oder behauenem Stein, deren raue Haptik durch das einfallende Tageslicht betont wird. Die Vegetation besteht aus standortgerechten Pflanzen, deren Blattformen und Grüntöne differenziert dargestellt sind, ohne sie zu idealisieren. Der Boden weist natürliche Unebenheiten, feinen Staub und kleine Kiesel auf, die dem Bild eine physische Präsenz verleihen. Die Lichtführung erzeugt deutliche Schattenwürfe, die die plastische Tiefe der Umgebung definieren. Alle kulturellen Merkmale werden als funktionale Bestandteile des Alltagslebens gezeigt, wobei die materielle Beschaffenheit von Textilien und Gebrauchsgegenständen im Vordergrund steht. Die gesamte Komposition wirkt sachlich und dokumentarisch, indem sie die spezifischen Umweltbedingungen und die vorhandene Infrastruktur neutral wiedergibt."),

    # --- Yoruba text + late iterations (17:19-17:40) ---
    (    7312.9, "qwen_img2img", "Yipada aworan yi si apejuwe ibi ti o r\u1eb9wa nibi ti a ti r\u00ed aw\u1ecdn ile ti a k\u1ecd p\u1eb9lu ilana i\u1e63\u1eb9-\u1ecdna ti aw\u1ecdn ti o pada de lati il\u1eb9 Brazil mu w\u00e1 si il\u1eb9 Naijiria. Ni iwaju aworan yii, j\u1eb9 ki a r\u00ed aw\u1ecdn eniyan ti w\u1ecdn w\u1ecd a\u1e63\u1ecd \u00f2k\u00e8 ti a hun p\u1eb9lu \u1ecdw\u1ecd, eyi ti o ni aw\u1ecdn ilana riran ti o l\u1eb9wa lori r\u1eb9. Aw\u1ecdn \u1ecdkunrin ninu aworan yii w\u1ecd agbada ati fila, nigba ti aw\u1ecdn obinrin w\u1ecd iro ati buba p\u1eb9lu gele ti a w\u00e9 daradara. Ni ab\u1eb9l\u1eb9 aworan naa, j\u1eb9 ki a r\u00ed aw\u1ecdn \u1ecdk\u1ecd nla ti ile-i\u1e63\u1eb9 Dangote ti o duro nitosi aw\u1ecdn ile itaja, eyi ti o n fihan idagbasoke \u1ecdr\u1ecd-aje ati i\u1e63owo ni agbegbe naa. Gbogbo ohun ti o wa ninu aworan yii gb\u1ecdd\u1ecd \u1e63e afihan a\u1e63a ati igbesi aye ode-oni ni il\u1eb9 Yoruba p\u1eb9lu it\u1ecdju ohun-ini atij\u1ecd."),
    (    8098.9, "qwen_img2img", "Make a plant out this image.It should be\u2026\n=It should be a Flower.Use the image\n=It should be Green \n=It should be real\n=There should be a bee fling over the flower\n=behind the flower should be a rabbit \n=the backround should be a blue sky with the sun and the clouds\n=in the corner there should be the text in cursive:Frohe Ostern\n=In a another corner there should be a a Easter egg with bright colours\n=The land must have grass\n=it should look photorealistic\n=it should look like the form like in image"),
    (    8197.7, "qwen_img2img", "Make it look like a superhero"),
    (    8417.1, "qwen_img2img", "In diesem Bild wird die Szenerie in eine detaillierte Landschaftsdarstellung übertragen. Die Architektur im Bild orientiert sich an funktionalen Bauweisen, wie sie in städtischen Randgebieten vorkommen, wobei die Oberflächenbeschaffenheit von Beton, Glas und Metall im Vordergrund steht. Die Vegetation wird als eine Mischung aus einheimischen Gräsern und Sträuchern dargestellt, die sich zwischen den baulichen Strukturen ausbreiten. Das Licht im Bild entspricht einer natürlichen Tageslichtsituation, die Schattenwürfe auf den Boden und die Fassaden erzeugt, wodurch die geometrischen Formen der Umgebung betont werden. Die Farbkombinationen bleiben gedeckt und orientieren sich an natürlichen Erdtönen sowie industriellen Graustufen. Alle Elemente im Bild sind klar voneinander abgegrenzt, um eine sachliche und räumlich tiefe Perspektive zu schaffen, die den Fokus auf die Materialität und die räumliche Anordnung der Objekte legt."),
    (    8505.4, "wan22_i2v_video", "Make it look like it gets built by cartoons"),
    (    8588.1, "wan22_i2v_video", "Make it look like it gets built by cartoons"),
    (    8594.6, "qwen_img2img", "In diesem Bild wird das Motiv in eine sachliche und detaillierte Szenerie überführt, die den Fokus auf materielle Texturen und räumliche Tiefe legt. Die Umgebung zeichnet sich durch eine klare, dokumentarische Perspektive aus, bei der architektonische Elemente oder natürliche Oberflächen ohne künstliche Dramatisierung dargestellt werden. Die Beleuchtung in der Szene wirkt natürlich und gleichmäßig, wodurch feine Details wie die Beschaffenheit von Stein, Holz oder Textilien hervorgehoben werden. Farbtöne sind gedämpft und orientieren sich an realen Vorbildern, um eine geerdete Atmosphäre zu schaffen. Alle kulturellen Bezüge im Bild werden respektvoll und als integraler Bestandteil des Alltagslebens präsentiert, wobei auf jegliche klischeehafte Übersteigerung verzichtet wird. Die Komposition leitet den Blick des Betrachters ruhig durch den Raum und betont die funktionale Schönheit der abgebildeten Objekte und deren Platzierung im Kontext ihrer Umgebung."),
]

assert len(WORKSHOP_REQUESTS) == 53, f"Expected 53 requests, got {len(WORKSHOP_REQUESTS)}"


# --- Configs that need img2img input ---
# wan22_i2v_video is IMAGE-to-video — it needs input_image just like qwen_img2img!
IMG2IMG_CONFIGS = {"qwen_img2img", "wan22_i2v_video"}
# qwen_2511_multi uses input_image1/2/3 (from device history), not input_image
MULTI_IMG_CONFIGS = {"qwen_2511_multi"}
# flux2 is text-to-image (no input_image needed)
# hunyuan3d_text_to_3d is text-to-3D (no input_image needed)


def compute_adjusted_offsets(max_gap: float) -> list[float]:
    """Cap inter-request gaps at max_gap seconds while preserving burst timing.

    Gaps > drain_threshold are marked as drain points (returned separately).
    At drain points the simulation waits for all pending requests to finish,
    then continues immediately — no artificial waiting.
    """
    if max_gap <= 0:
        return [offset for offset, _, _ in WORKSHOP_REQUESTS]

    adjusted = [0.0]
    for i in range(1, len(WORKSHOP_REQUESTS)):
        raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
        capped_gap = min(raw_gap, max_gap)
        adjusted.append(adjusted[-1] + capped_gap)
    return adjusted


def find_drain_points(max_gap: float) -> set[int]:
    """Find indices where the original gap was capped (i.e. original > max_gap).

    At these points the queue had time to clear in the real workshop,
    so we drain all pending requests before continuing.
    """
    if max_gap <= 0:
        return set()
    drain_at: set[int] = set()
    for i in range(1, len(WORKSHOP_REQUESTS)):
        raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
        if raw_gap > max_gap:
            drain_at.add(i)
    return drain_at


@dataclass
class RequestResult:
    index: int
    config: str
    prompt: str
    status: str  # success, error, timeout, blocked
    duration_ms: float
    error: Optional[str] = None
    queue_rejected: bool = False


async def upload_test_image(session: aiohttp.ClientSession, base_url: str, image_path: str) -> Optional[str]:
    """Upload a test image and return its path for img2img use."""
    if not os.path.exists(image_path):
        print(f"  WARNING: Test image not found: {image_path}")
        return None

    url = f"{base_url}/api/media/upload/image"
    data = aiohttp.FormData()
    data.add_field("file", open(image_path, "rb"), filename="loadtest_input.png", content_type="image/png")

    try:
        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                result = await resp.json()
                path = result.get("image_path", "")
                print(f"  Uploaded test image: {path}")
                return path
            else:
                print(f"  WARNING: Image upload failed ({resp.status})")
                return None
    except Exception as e:
        print(f"  WARNING: Image upload error: {e}")
        return None


async def send_request(
    session: aiohttp.ClientSession,
    base_url: str,
    index: int,
    config: str,
    prompt: str,
    device_id: str,
    no_image: bool = False,
    input_image_path: Optional[str] = None,
) -> RequestResult:
    """Send a single generation request via SSE and wait for completion."""
    start = time.monotonic()

    # For img2img/i2v without an actual image, fall back to sd35_large (t2i)
    effective_config = config
    if config in IMG2IMG_CONFIGS and (no_image or not input_image_path):
        effective_config = "sd35_large"

    params = {
        "output_config": effective_config,
        "input_text": prompt,
        "prompt": prompt,
        "enable_streaming": "true",
        "device_id": device_id,
    }

    # Add input_image for single img2img and i2v configs
    if effective_config in IMG2IMG_CONFIGS and input_image_path:
        params["input_image"] = input_image_path

    # Add input_image1/2/3 for multi-image configs (same image 3x for load test)
    if effective_config in MULTI_IMG_CONFIGS and input_image_path:
        params["input_image1"] = input_image_path
        params["input_image2"] = input_image_path
        params["input_image3"] = input_image_path

    url = f"{base_url}/api/schema/pipeline/generation"

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            status = "unknown"
            error = None
            queue_rejected = False
            current_event = ""

            # SSE format: "event: <type>\ndata: <json>\n\n"
            # Must track event type across lines
            async for line in resp.content:
                text = line.decode("utf-8", errors="replace").strip()

                if not text:
                    current_event = ""
                    continue

                if text.startswith("event:"):
                    current_event = text[6:].strip()
                    continue

                if text.startswith(":"):
                    continue  # SSE comment / heartbeat

                if not text.startswith("data:"):
                    continue

                data_str = text[5:].strip()
                if not data_str:
                    continue

                try:
                    import json
                    data = json.loads(data_str)
                except Exception:
                    continue

                event_type = current_event or data.get("type", "")

                if event_type == "complete":
                    media_status = data.get("status", "")
                    media = data.get("media_output", {})
                    if media_status == "error" or (isinstance(media, dict) and media.get("status") == "error"):
                        status = "error"
                        error = media.get("error") or data.get("message", "unknown")
                        if "queue full" in (error or "").lower():
                            queue_rejected = True
                    else:
                        status = "success"
                    break

                elif event_type == "blocked":
                    status = "blocked"
                    error = data.get("reason", "safety")
                    break

                elif event_type == "error":
                    status = "error"
                    error = data.get("message", "unknown")
                    if "queue full" in (error or "").lower():
                        queue_rejected = True
                    break

                current_event = ""

            duration = (time.monotonic() - start) * 1000
            return RequestResult(index, effective_config, prompt, status, duration, error, queue_rejected)

    except asyncio.TimeoutError:
        duration = (time.monotonic() - start) * 1000
        return RequestResult(index, effective_config, prompt, "timeout", duration, "Client timeout (600s)")
    except Exception as e:
        duration = (time.monotonic() - start) * 1000
        return RequestResult(index, effective_config, prompt, "error", duration, str(e))


async def run_simulation(port: int, dry_run: bool, no_image: bool, image_path: str, max_gap: float = 15.0):
    base_url = f"http://localhost:{port}"
    adjusted = compute_adjusted_offsets(max_gap)
    drain_points = find_drain_points(max_gap)
    original_duration = WORKSHOP_REQUESTS[-1][0]
    adjusted_duration = adjusted[-1]
    saved = original_duration - adjusted_duration

    print(f"{'='*70}")
    print(f"  Workshop Load Replay \u2014 2026-03-27")
    print(f"  Target: {base_url}")
    print(f"  Max gap: {max_gap}s  (drain queue at every capped pause, {len(drain_points)} drain points)")
    print(f"  Mode:   {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Image:  {'skip (t2i only)' if no_image else f'img2img/i2v with {image_path}'}")
    print(f"  Requests: {len(WORKSHOP_REQUESTS)}")
    print(f"{'='*70}")
    print()

    # Config distribution
    from collections import Counter
    configs = Counter(c for _, c, _ in WORKSHOP_REQUESTS)
    print(f"  Config distribution:")
    for cfg, cnt in configs.most_common():
        print(f"    {cfg:30s} {cnt:3d}")
    print()

    if dry_run:
        print("Timing preview (no requests sent):")
        for i, ((_offset, config, prompt), adj_offset) in enumerate(zip(WORKSHOP_REQUESTS, adjusted)):
            gap_orig = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0] if i > 0 else 0
            drain = " [DRAIN QUEUE]" if i in drain_points else ""
            print(f"  T+{adj_offset:7.1f}s  {config:25s}  {prompt[:45]}{drain}")
        print(f"\nOriginal duration: {original_duration:.0f}s  |  Adjusted: {adjusted_duration:.0f}s  (+ drain waits)")
        return

    # Check server reachability
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    print(f"ERROR: Server returned {resp.status}")
                    return
        except Exception as e:
            print(f"ERROR: Cannot reach {base_url}: {e}")
            return

    print(f"Server reachable.")

    # Check ComfyUI reachability (needed for qwen_img2img, wan22_i2v_video, qwen_2511_multi, flux2)
    comfyui_needed = any(c in ("qwen_img2img", "wan22_i2v_video", "qwen_2511_multi", "flux2") for _, c, _ in WORKSHOP_REQUESTS)
    if comfyui_needed:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:17804/system_stats", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        print(f"ComfyUI reachable (port 17804).")
                    else:
                        print(f"WARNING: ComfyUI returned {resp.status} \u2014 ComfyUI configs may fail")
        except Exception:
            print(f"WARNING: ComfyUI not reachable on port 17804 \u2014 ComfyUI configs may fail")
            print(f"  DevServer COMFYUI-MANAGER may auto-start it, but first requests could fail.")

    # Check GPU Service reachability (needed for sd35_large, hunyuan3d_text_to_3d)
    gpu_needed = any(c in ("sd35_large", "hunyuan3d_text_to_3d") for _, c, _ in WORKSHOP_REQUESTS)
    if gpu_needed:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:17803/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        print(f"GPU Service reachable (port 17803).")
                    else:
                        print(f"WARNING: GPU Service returned {resp.status} \u2014 sd35_large/hunyuan3d may fail")
        except Exception:
            print(f"WARNING: GPU Service not reachable on port 17803 \u2014 sd35_large/hunyuan3d may fail")

    # Upload test image for img2img and i2v
    input_image_ref = None
    if not no_image:
        async with aiohttp.ClientSession() as session:
            input_image_ref = await upload_test_image(session, base_url, image_path)
            if not input_image_ref:
                print("  Falling back to t2i only (no image uploaded)")
                no_image = True

    print(f"Starting replay...\n")

    # Device pool: 7 devices, each can only run 1 generation at a time.
    # Like real workshop — each iPad waits for its result before submitting again.
    N_DEVICES = 7
    device_locks: list[asyncio.Lock] = [asyncio.Lock() for _ in range(N_DEVICES)]
    device_ids = [f"loadtest_{d}" for d in range(N_DEVICES)]
    results: list[RequestResult] = []
    results_lock = asyncio.Lock()
    tasks: list[asyncio.Task] = []
    sim_start = time.monotonic()

    async def send_with_device(session, i, config, prompt, adj_offset):
        """Acquire a free device, wait for timing, send request, release device."""
        # Wait until the right moment first
        target_time = adj_offset
        now = time.monotonic() - sim_start
        wait = target_time - now
        if wait > 0:
            await asyncio.sleep(wait)

        # Find a free device (round-robin preference, take first available)
        preferred = i % N_DEVICES
        device_idx = None

        # Try preferred device first (non-blocking)
        if not device_locks[preferred].locked():
            device_idx = preferred
        else:
            # Try all others
            for d in range(N_DEVICES):
                if not device_locks[d].locked():
                    device_idx = d
                    break

        # If all busy, wait for preferred device
        if device_idx is None:
            device_idx = preferred

        async with device_locks[device_idx]:
            elapsed = time.monotonic() - sim_start
            print(f"[T+{elapsed:7.1f}s] #{i+1:3d} SEND  dev{device_idx}  {config:25s}  {prompt[:45]}")

            result = await send_request(
                session, base_url, i, config, prompt,
                device_ids[device_idx], no_image, input_image_ref
            )

            elapsed = time.monotonic() - sim_start
            tag = f"{result.status.upper()}"
            if result.error:
                tag += f" ({result.error[:40]})"
            print(f"[T+{elapsed:7.1f}s] #{i+1:3d} {tag:50s} {result.duration_ms/1000:.1f}s  {config}")

            async with results_lock:
                results.append(result)

    async with aiohttp.ClientSession() as session:
        for i, ((_offset, config, prompt), adj_offset) in enumerate(zip(WORKSHOP_REQUESTS, adjusted)):
            # Drain point: long original pause — wait for all pending, then reset clock
            if i in drain_points and tasks:
                raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
                elapsed = time.monotonic() - sim_start
                print(f"\n[T+{elapsed:7.1f}s] --- DRAIN POINT (original gap {raw_gap:.0f}s) \u2014 waiting for {sum(1 for t in tasks if not t.done())} pending... ---")
                await asyncio.gather(*tasks)
                # Reset the clock: adjust all remaining offsets relative to now
                drain_base = time.monotonic() - sim_start
                for j in range(i, len(adjusted)):
                    adjusted[j] = drain_base + (adjusted[j] - adjusted[i])
                elapsed = time.monotonic() - sim_start
                print(f"[T+{elapsed:7.1f}s] --- DRAIN COMPLETE \u2014 continuing immediately ---\n")

            task = asyncio.create_task(
                send_with_device(session, i, config, prompt, adjusted[i])
            )
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

    # Sort results by index
    results.sort(key=lambda r: r.index)

    # --- Report ---
    total_time = time.monotonic() - sim_start
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}\n")

    success = [r for r in results if r.status == "success"]
    blocked = [r for r in results if r.status == "blocked"]
    errors = [r for r in results if r.status == "error"]
    timeouts = [r for r in results if r.status == "timeout"]
    queue_rej = [r for r in results if r.queue_rejected]

    print(f"  Total requests:     {len(results)}")
    print(f"  Success:            {len(success)} ({100*len(success)/len(results):.0f}%)")
    print(f"  Blocked (safety):   {len(blocked)} ({100*len(blocked)/len(results):.0f}%)")
    print(f"  Errors:             {len(errors)} ({100*len(errors)/len(results):.0f}%)")
    print(f"  Timeouts:           {len(timeouts)} ({100*len(timeouts)/len(results):.0f}%)")
    print(f"  Queue rejected:     {len(queue_rej)} ({100*len(queue_rej)/len(results):.0f}%)")
    print()

    if success:
        durations = [r.duration_ms for r in success]
        print(f"  Success latency:")
        print(f"    Min:    {min(durations)/1000:.1f}s")
        print(f"    Median: {sorted(durations)[len(durations)//2]/1000:.1f}s")
        print(f"    Max:    {max(durations)/1000:.1f}s")
        print(f"    Avg:    {sum(durations)/len(durations)/1000:.1f}s")
    print()

    # Per-config breakdown
    config_results: dict[str, list[RequestResult]] = {}
    for r in results:
        config_results.setdefault(r.config, []).append(r)

    print(f"  Per-config breakdown:")
    for cfg in sorted(config_results.keys()):
        cfg_list = config_results[cfg]
        cfg_success = sum(1 for r in cfg_list if r.status == "success")
        cfg_durations = [r.duration_ms for r in cfg_list if r.status == "success"]
        avg_s = f"{sum(cfg_durations)/len(cfg_durations)/1000:.1f}s" if cfg_durations else "-"
        print(f"    {cfg:25s}  {cfg_success}/{len(cfg_list)} success  avg={avg_s}")
    print()

    print(f"  Wall time: {total_time:.0f}s")
    print()

    # Print errors
    if errors:
        print(f"  Error details:")
        for r in errors:
            tag = " [QUEUE FULL]" if r.queue_rejected else ""
            print(f"    #{r.index+1:3d} {r.config:25s} {r.duration_ms/1000:.1f}s  {tag}")
            print(f"         {r.error}")
        print()

    if timeouts:
        print(f"  Timeout details:")
        for r in timeouts:
            print(f"    #{r.index+1:3d} {r.config:25s} {r.duration_ms/1000:.0f}s  {r.error}")
        print()

    if blocked:
        print(f"  Blocked details:")
        for r in blocked:
            print(f"    #{r.index+1:3d} {r.config:25s} {r.prompt[:60]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Workshop Load Replay \u2014 2026-03-27")
    parser.add_argument("--port", type=int, default=17802, help="Backend port (default: 17802)")
    parser.add_argument("--dry-run", action="store_true", help="Print timing only, no requests")
    parser.add_argument("--no-image", action="store_true", help="Skip img2img/i2v, use sd35_large fallback")
    parser.add_argument("--image", type=str,
                        default="/home/joerissen/Pictures/Flux2_randomPrompt_ClaudeSonnet4.5/ComfyUI_00591_.png",
                        help="Test image for img2img/i2v")
    parser.add_argument("--max-gap", type=float, default=15.0,
                        help="Cap idle gaps between requests (default: 15s). Queue drains at every capped pause.")
    args = parser.parse_args()

    asyncio.run(run_simulation(args.port, args.dry_run, args.no_image, args.image, args.max_gap))


if __name__ == "__main__":
    main()
