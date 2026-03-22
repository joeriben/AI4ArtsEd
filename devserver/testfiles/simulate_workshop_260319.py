#!/usr/bin/env python3
"""
Workshop Load Replay — 2026-03-19

Replays the 219 Stage-4 generations from the largest recorded workshop with
the original timing pattern. SD3.5-dominated session (96% sd35_large) with
extreme burst density — 12 concurrent requests within 0.7s at peak.

Extracted from: Teilprotokoll 19 3 2026 backend.txt
Workshop window: 13:03 - 15:15 (2h 12min active generation)
Prompts are synthetic but realistic length (load pattern is what matters).

Usage:
    python simulate_workshop_260319.py [--port 17802] [--fast] [--dry-run] [--max-gap 15]

    --port PORT       Backend port (default: 17802 = development)
    --fast            Run at 4x speed
    --dry-run         Print timing without sending requests
    --no-image        Skip img2img (use sd35_large fallback)
    --max-gap SECONDS Cap inter-request idle gaps (default: 15s, 0=no cap)

HOW THIS SCRIPT WAS CREATED (for future sessions creating similar scripts):
    1. Parse the backend log for [STAGE4-GEN] lines to get timestamps + output_configs:
       grep "[STAGE4-GEN] Executing generation with config" backend.txt
    2. Compute offsets from first timestamp (13:03:56)
    3. Generate synthetic prompts at REALISTIC LENGTH (~8-20 words, matching typical
       workshop input). Short prompts (3 words) produce unrealistically fast LLM
       responses and don't represent real load.
    4. Copy the script structure from the previous replay script (SSE parsing,
       aiohttp, RequestResult, etc.)
    5. This takes ~10 minutes, not hours. It's a grep + paste job.
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


# --- Workshop replay data (extracted from backend log 2026-03-19) ---
# Format: (seconds_offset_from_start, output_config, german_prompt)
# Offset 0 = 13:03:56 (first Stage 4 generation)
# 219 entries = all requests that reached Stage 4 in workshop window (13:03-15:15)
# Prompts are synthetic — only timing + config distribution matters
# Key characteristic: extreme SD3.5 dominance (96%), burst of 12 requests in 0.7s

WORKSHOP_REQUESTS = [
    (      0.0, "gpt_image_1", "Color photography 1960s style slightly faded Kodachrome film grain vibrant natural scene"),
    (     28.8, "flux2_diffusers", "1960s Kodachrome color photograph film grain a beautiful fish swimming in a large glass bowl"),
    (     77.7, "flux2_diffusers", "Color photography documentary style natural light hands working with clay on pottery wheel"),
    (   3109.6, "qwen_img2img", "Mach die Farben kraeftiger und den Hintergrund etwas dunkler bitte"),
    (   3370.9, "sd35_large", "Zwei Kinder wandern durch einen Wald mit hohen Baeumen und Sonnenlicht"),
    (   3371.5, "sd35_large", "Ein Stuhl der auf einem Tisch steht in einem leeren Raum beleuchtet"),
    (   3405.9, "sd35_large", "Geometrische Formen die sich ueberlappen auf weissem Hintergrund mit Schatten"),
    (   3543.1, "sd35_large", "Ein Kreis und ein Dreieck die zusammen eine neue Form bilden bunt"),
    (   3544.2, "sd35_large", "Gelbe Blumen auf einer gruenen Wiese mit blauem Himmel und Wolken"),
    (   3544.3, "sd35_large", "Ein Hund der neben einem Kind sitzt auf einer Bank im Park"),
    (   3545.1, "sd35_large", "Abstrakte Linien die sich kreuzen in verschiedenen Farben auf schwarzem Grund"),
    (   3548.3, "sd35_large", "Ein Fenster durch das Sonnenlicht in einen dunklen Raum faellt warm"),
    (   3549.7, "sd35_large", "Haende die ein Blatt Papier halten mit einer Zeichnung darauf klar"),
    (   3552.1, "sd35_large", "Ein roter Apfel auf einem weissen Teller mit einem Messer daneben"),
    (   3555.4, "sd35_large", "Berge im Hintergrund mit einem See davor und Baeumen am Ufer"),
    (   3556.8, "sd35_large", "Ein altes Fahrrad das an einer Mauer lehnt mit Blumen drumherum"),
    (   3557.7, "sd35_large", "Sterne am Nachthimmel ueber einer kleinen Stadt mit beleuchteten Fenstern"),
    (   3561.3, "sd35_large", "Ein Vogel der auf einem Ast sitzt und in die Ferne schaut"),
    (   3562.2, "sd35_large", "Regen der auf eine Fensterscheibe faellt mit verschwommenen Lichtern draussen"),
    (   3601.6, "sd35_large", "Ein Kind das mit Kreide auf den Boden malt bunte Figuren gross"),
    (   3613.7, "sd35_large", "Zwei Haende die ein Herz formen vor einem Sonnenuntergang am Meer"),
    (   3614.3, "sd35_large", "Ein Buch das aufgeschlagen auf einem Holztisch liegt mit Kerze daneben"),
    (   3624.1, "sd35_large", "Bunte Luftballons die in den blauen Himmel steigen ueber einer Stadt"),
    (   3624.1, "sd35_large", "Ein Schmetterling der auf einer roten Blume sitzt im Sonnenlicht warm"),
    (   3633.3, "sd35_large", "Ein Leuchtturm am Meer bei Nacht mit Sternen und Mondschein hell"),
    (   3639.9, "sd35_large", "Alte Treppe die nach oben fuehrt mit Pflanzen an den Seiten"),
    (   3799.4, "sd35_large", "Ein Baum der alleine auf einem Huegel steht bei Sonnenuntergang orange"),
    (   3811.6, "sd35_large", "Schuhe die auf einer nassen Strasse stehen mit Pfuetzen und Regen"),
    (   3813.4, "sd35_large", "Ein Zug der durch eine verschneite Landschaft faehrt mit Bergen hinten"),
    (   3814.0, "sd35_large", "Haende die Ton formen auf einer Toepferscheibe die sich schnell dreht"),
    (   3838.3, "sd35_large", "Ein Spiegel in dem man einen Garten sieht mit bunten Blumen drin"),
    (   3840.1, "sd35_large", "Kinder die zusammen ein grosses Bild malen auf dem Boden kniend"),
    (   3845.9, "sd35_large", "Ein alter Koffer der offen steht mit Postkarten und Fotos darin"),
    (   3849.5, "sd35_large", "Muscheln am Strand mit Wellen die sanft ans Ufer kommen leise"),
    (   3872.7, "sd35_large", "Ein Papierflugzeug das durch einen blauen Himmel mit Wolken fliegt weit"),
    (   3875.8, "sd35_large", "Farben die ineinander verlaufen wie bei einem Aquarell weich und fliessend"),
    (   3880.1, "sd35_large", "Ein Fahrrad mit einem Korb voller Blumen auf einem Feldweg sonnig"),
    (   3885.4, "sd35_large", "Treppen die in verschiedene Richtungen fuehren wie bei Escher surreal verschlungen"),
    (   3890.3, "sd35_large", "Ein Glas Wasser das auf einem Fensterbrett steht mit Licht hindurch"),
    (   3894.6, "sd35_large", "Kinder die im Regen tanzen mit bunten Gummistiefeln und Regenjacken froh"),
    (   3899.8, "sd35_large", "Ein alter Schluessel auf einem Holztisch mit Moos und Blaettern drumherum"),
    (   3900.1, "sd35_large", "Wolken die wie Tiere aussehen an einem blauen Sommerhimmel flauschig weiss"),
    (   3916.4, "sd35_large", "Ein Kuenstler der vor einer leeren Leinwand steht mit Pinsel bereit"),
    (   3918.7, "sd35_large", "Pflastersteine auf denen Kreidezeichnungen zu sehen sind bunt und kindlich schoen"),
    (   3922.7, "sd35_large", "Zwei Kinder wandern durch einen Wald mit hohen Baeumen und Sonnenlicht"),
    (   3925.0, "sd35_large", "Ein Stuhl der auf einem Tisch steht in einem leeren Raum beleuchtet"),
    (   4152.1, "sd35_large", "Geometrische Formen die sich ueberlappen auf weissem Hintergrund mit Schatten"),
    (   4154.5, "sd35_large", "Ein Kreis und ein Dreieck die zusammen eine neue Form bilden bunt"),
    (   4157.0, "sd35_large", "Gelbe Blumen auf einer gruenen Wiese mit blauem Himmel und Wolken"),
    (   4162.3, "sd35_large", "Ein Hund der neben einem Kind sitzt auf einer Bank im Park"),
    (   4164.5, "sd35_large", "Abstrakte Linien die sich kreuzen in verschiedenen Farben auf schwarzem Grund"),
    (   4186.4, "sd35_large", "Ein Fenster durch das Sonnenlicht in einen dunklen Raum faellt warm"),
    (   4187.6, "sd35_large", "Haende die ein Blatt Papier halten mit einer Zeichnung darauf klar"),
    (   4192.8, "sd35_large", "Ein roter Apfel auf einem weissen Teller mit einem Messer daneben"),
    (   4224.9, "sd35_large", "Berge im Hintergrund mit einem See davor und Baeumen am Ufer"),
    (   4227.9, "sd35_large", "Ein altes Fahrrad das an einer Mauer lehnt mit Blumen drumherum"),
    (   4235.7, "sd35_large", "Sterne am Nachthimmel ueber einer kleinen Stadt mit beleuchteten Fenstern"),
    (   4261.5, "sd35_large", "Ein Vogel der auf einem Ast sitzt und in die Ferne schaut"),
    (   4291.3, "qwen_img2img", "Aendere den Hintergrund in eine andere Jahreszeit bitte Fruehling waere schoen"),
    (   4322.6, "sd35_large", "Regen der auf eine Fensterscheibe faellt mit verschwommenen Lichtern draussen"),
    (   4324.9, "sd35_large", "Ein Kind das mit Kreide auf den Boden malt bunte Figuren gross"),
    (   4326.0, "sd35_large", "Zwei Haende die ein Herz formen vor einem Sonnenuntergang am Meer"),
    (   4326.3, "sd35_large", "Ein Buch das aufgeschlagen auf einem Holztisch liegt mit Kerze daneben"),
    (   4377.6, "sd35_large", "Bunte Luftballons die in den blauen Himmel steigen ueber einer Stadt"),
    (   4377.7, "sd35_large", "Ein Schmetterling der auf einer roten Blume sitzt im Sonnenlicht warm"),
    (   4379.4, "sd35_large", "Ein Leuchtturm am Meer bei Nacht mit Sternen und Mondschein hell"),
    (   4384.2, "qwen_img2img", "Mach das ganze Bild so als waere es mit Wasserfarben gemalt worden"),
    (   4452.8, "sd35_large", "Alte Treppe die nach oben fuehrt mit Pflanzen an den Seiten"),
    (   4454.4, "sd35_large", "Ein Baum der alleine auf einem Huegel steht bei Sonnenuntergang orange"),
    (   4472.0, "sd35_large", "Schuhe die auf einer nassen Strasse stehen mit Pfuetzen und Regen"),
    (   4473.1, "sd35_large", "Ein Zug der durch eine verschneite Landschaft faehrt mit Bergen hinten"),
    (   4475.4, "sd35_large", "Haende die Ton formen auf einer Toepferscheibe die sich schnell dreht"),
    (   4477.2, "sd35_large", "Ein Spiegel in dem man einen Garten sieht mit bunten Blumen drin"),
    (   4480.0, "sd35_large", "Kinder die zusammen ein grosses Bild malen auf dem Boden kniend"),
    (   4531.7, "sd35_large", "Ein alter Koffer der offen steht mit Postkarten und Fotos darin"),
    (   4532.4, "sd35_large", "Muscheln am Strand mit Wellen die sanft ans Ufer kommen leise"),
    (   4533.7, "sd35_large", "Ein Papierflugzeug das durch einen blauen Himmel mit Wolken fliegt weit"),
    (   4534.5, "sd35_large", "Farben die ineinander verlaufen wie bei einem Aquarell weich und fliessend"),
    (   4556.9, "sd35_large", "Ein Fahrrad mit einem Korb voller Blumen auf einem Feldweg sonnig"),
    (   4559.0, "sd35_large", "Treppen die in verschiedene Richtungen fuehren wie bei Escher surreal verschlungen"),
    (   4559.3, "sd35_large", "Ein Glas Wasser das auf einem Fensterbrett steht mit Licht hindurch"),
    (   4559.4, "sd35_large", "Kinder die im Regen tanzen mit bunten Gummistiefeln und Regenjacken froh"),
    (   4559.4, "sd35_large", "Ein alter Schluessel auf einem Holztisch mit Moos und Blaettern drumherum"),
    (   4559.4, "sd35_large", "Wolken die wie Tiere aussehen an einem blauen Sommerhimmel flauschig weiss"),
    (   4559.4, "sd35_large", "Ein Kuenstler der vor einer leeren Leinwand steht mit Pinsel bereit"),
    (   4573.0, "sd35_large", "Pflastersteine auf denen Kreidezeichnungen zu sehen sind bunt und kindlich schoen"),
    (   4573.1, "sd35_large", "Zwei Kinder wandern durch einen Wald mit hohen Baeumen und Sonnenlicht"),
    (   4583.9, "sd35_large", "Ein Stuhl der auf einem Tisch steht in einem leeren Raum beleuchtet"),
    (   4599.2, "sd35_large", "Geometrische Formen die sich ueberlappen auf weissem Hintergrund mit Schatten"),
    (   4600.5, "sd35_large", "Ein Kreis und ein Dreieck die zusammen eine neue Form bilden bunt"),
    (   4604.5, "sd35_large", "Gelbe Blumen auf einer gruenen Wiese mit blauem Himmel und Wolken"),
    (   4607.9, "sd35_large", "Ein Hund der neben einem Kind sitzt auf einer Bank im Park"),
    (   4610.6, "sd35_large", "Abstrakte Linien die sich kreuzen in verschiedenen Farben auf schwarzem Grund"),
    (   4614.7, "sd35_large", "Ein Fenster durch das Sonnenlicht in einen dunklen Raum faellt warm"),
    (   4618.8, "sd35_large", "Haende die ein Blatt Papier halten mit einer Zeichnung darauf klar"),
    (   4630.6, "sd35_large", "Ein roter Apfel auf einem weissen Teller mit einem Messer daneben"),
    (   4632.5, "sd35_large", "Berge im Hintergrund mit einem See davor und Baeumen am Ufer"),
    (   4638.6, "sd35_large", "Ein altes Fahrrad das an einer Mauer lehnt mit Blumen drumherum"),
    (   4735.2, "sd35_large", "Sterne am Nachthimmel ueber einer kleinen Stadt mit beleuchteten Fenstern"),
    (   4793.4, "sd35_large", "Ein Vogel der auf einem Ast sitzt und in die Ferne schaut"),
    (   4852.5, "qwen_img2img", "Fuege mehr Details im Vordergrund hinzu damit es plastischer wirkt"),
    (   4871.9, "sd35_large", "Regen der auf eine Fensterscheibe faellt mit verschwommenen Lichtern draussen"),
    (   4918.6, "qwen_img2img", "Mach die Schatten weicher und das Licht waermer wie am Abend"),
    (   4972.9, "sd35_large", "Ein Kind das mit Kreide auf den Boden malt bunte Figuren gross"),
    (   4980.3, "sd35_large", "Zwei Haende die ein Herz formen vor einem Sonnenuntergang am Meer"),
    (   5086.2, "sd35_large", "Ein Buch das aufgeschlagen auf einem Holztisch liegt mit Kerze daneben"),
    (   5124.9, "sd35_large", "Bunte Luftballons die in den blauen Himmel steigen ueber einer Stadt"),
    (   5140.8, "sd35_large", "Ein Schmetterling der auf einer roten Blume sitzt im Sonnenlicht warm"),
    (   5186.2, "sd35_large", "Ein Leuchtturm am Meer bei Nacht mit Sternen und Mondschein hell"),
    (   5207.4, "sd35_large", "Alte Treppe die nach oben fuehrt mit Pflanzen an den Seiten"),
    (   5228.6, "sd35_large", "Ein Baum der alleine auf einem Huegel steht bei Sonnenuntergang orange"),
    (   5262.1, "sd35_large", "Schuhe die auf einer nassen Strasse stehen mit Pfuetzen und Regen"),
    (   5263.5, "qwen_img2img", "Veraendere die Perspektive als wuerde man von oben draufschauen bitte"),
    (   5263.6, "sd35_large", "Ein Zug der durch eine verschneite Landschaft faehrt mit Bergen hinten"),
    (   5319.0, "sd35_large", "Haende die Ton formen auf einer Toepferscheibe die sich schnell dreht"),
    (   5319.3, "sd35_large", "Ein Spiegel in dem man einen Garten sieht mit bunten Blumen drin"),
    (   5353.0, "sd35_large", "Kinder die zusammen ein grosses Bild malen auf dem Boden kniend"),
    (   5389.9, "sd35_large", "Ein alter Koffer der offen steht mit Postkarten und Fotos darin"),
    (   5391.8, "sd35_large", "Muscheln am Strand mit Wellen die sanft ans Ufer kommen leise"),
    (   5395.2, "qwen_img2img", "Mach alles etwas abstrakter und reduziere die Details im Hintergrund"),
    (   5472.5, "sd35_large", "Ein Papierflugzeug das durch einen blauen Himmel mit Wolken fliegt weit"),
    (   5490.8, "sd35_large", "Farben die ineinander verlaufen wie bei einem Aquarell weich und fliessend"),
    (   5491.6, "sd35_large", "Ein Fahrrad mit einem Korb voller Blumen auf einem Feldweg sonnig"),
    (   5492.4, "sd35_large", "Treppen die in verschiedene Richtungen fuehren wie bei Escher surreal verschlungen"),
    (   5537.2, "sd35_large", "Ein Glas Wasser das auf einem Fensterbrett steht mit Licht hindurch"),
    (   5545.7, "sd35_large", "Kinder die im Regen tanzen mit bunten Gummistiefeln und Regenjacken froh"),
    (   5546.3, "sd35_large", "Ein alter Schluessel auf einem Holztisch mit Moos und Blaettern drumherum"),
    (   5546.8, "sd35_large", "Wolken die wie Tiere aussehen an einem blauen Sommerhimmel flauschig weiss"),
    (   5573.2, "sd35_large", "Ein Kuenstler der vor einer leeren Leinwand steht mit Pinsel bereit"),
    (   5577.5, "sd35_large", "Pflastersteine auf denen Kreidezeichnungen zu sehen sind bunt und kindlich schoen"),
    (   5580.6, "sd35_large", "Zwei Kinder wandern durch einen Wald mit hohen Baeumen und Sonnenlicht"),
    (   5643.3, "sd35_large", "Ein Stuhl der auf einem Tisch steht in einem leeren Raum beleuchtet"),
    (   5643.3, "sd35_large", "Geometrische Formen die sich ueberlappen auf weissem Hintergrund mit Schatten"),
    (   5643.4, "sd35_large", "Ein Kreis und ein Dreieck die zusammen eine neue Form bilden bunt"),
    (   5643.5, "sd35_large", "Gelbe Blumen auf einer gruenen Wiese mit blauem Himmel und Wolken"),
    (   5643.5, "sd35_large", "Ein Hund der neben einem Kind sitzt auf einer Bank im Park"),
    (   5643.6, "sd35_large", "Abstrakte Linien die sich kreuzen in verschiedenen Farben auf schwarzem Grund"),
    (   5643.6, "sd35_large", "Ein Fenster durch das Sonnenlicht in einen dunklen Raum faellt warm"),
    (   5643.7, "sd35_large", "Haende die ein Blatt Papier halten mit einer Zeichnung darauf klar"),
    (   5643.7, "sd35_large", "Ein roter Apfel auf einem weissen Teller mit einem Messer daneben"),
    (   5643.8, "sd35_large", "Berge im Hintergrund mit einem See davor und Baeumen am Ufer"),
    (   5643.8, "sd35_large", "Ein altes Fahrrad das an einer Mauer lehnt mit Blumen drumherum"),
    (   5643.9, "sd35_large", "Sterne am Nachthimmel ueber einer kleinen Stadt mit beleuchteten Fenstern"),
    (   5657.6, "sd35_large", "Ein Vogel der auf einem Ast sitzt und in die Ferne schaut"),
    (   5668.3, "sd35_large", "Regen der auf eine Fensterscheibe faellt mit verschwommenen Lichtern draussen"),
    (   5671.9, "sd35_large", "Ein Kind das mit Kreide auf den Boden malt bunte Figuren gross"),
    (   5676.1, "sd35_large", "Zwei Haende die ein Herz formen vor einem Sonnenuntergang am Meer"),
    (   5678.0, "sd35_large", "Ein Buch das aufgeschlagen auf einem Holztisch liegt mit Kerze daneben"),
    (   5678.9, "sd35_large", "Bunte Luftballons die in den blauen Himmel steigen ueber einer Stadt"),
    (   5716.0, "sd35_large", "Ein Schmetterling der auf einer roten Blume sitzt im Sonnenlicht warm"),
    (   5717.8, "sd35_large", "Ein Leuchtturm am Meer bei Nacht mit Sternen und Mondschein hell"),
    (   5721.3, "sd35_large", "Alte Treppe die nach oben fuehrt mit Pflanzen an den Seiten"),
    (   5724.5, "sd35_large", "Ein Baum der alleine auf einem Huegel steht bei Sonnenuntergang orange"),
    (   5724.8, "sd35_large", "Schuhe die auf einer nassen Strasse stehen mit Pfuetzen und Regen"),
    (   5729.5, "sd35_large", "Ein Zug der durch eine verschneite Landschaft faehrt mit Bergen hinten"),
    (   5731.5, "sd35_large", "Haende die Ton formen auf einer Toepferscheibe die sich schnell dreht"),
    (   5732.3, "sd35_large", "Ein Spiegel in dem man einen Garten sieht mit bunten Blumen drin"),
    (   5734.0, "sd35_large", "Kinder die zusammen ein grosses Bild malen auf dem Boden kniend"),
    (   5735.9, "sd35_large", "Ein alter Koffer der offen steht mit Postkarten und Fotos darin"),
    (   5740.0, "sd35_large", "Muscheln am Strand mit Wellen die sanft ans Ufer kommen leise"),
    (   5740.1, "sd35_large", "Ein Papierflugzeug das durch einen blauen Himmel mit Wolken fliegt weit"),
    (   5740.5, "sd35_large", "Farben die ineinander verlaufen wie bei einem Aquarell weich und fliessend"),
    (   5749.6, "sd35_large", "Ein Fahrrad mit einem Korb voller Blumen auf einem Feldweg sonnig"),
    (   5758.2, "sd35_large", "Treppen die in verschiedene Richtungen fuehren wie bei Escher surreal verschlungen"),
    (   5771.4, "sd35_large", "Ein Glas Wasser das auf einem Fensterbrett steht mit Licht hindurch"),
    (   5788.2, "sd35_large", "Kinder die im Regen tanzen mit bunten Gummistiefeln und Regenjacken froh"),
    (   5798.3, "sd35_large", "Ein alter Schluessel auf einem Holztisch mit Moos und Blaettern drumherum"),
    (   5802.4, "sd35_large", "Wolken die wie Tiere aussehen an einem blauen Sommerhimmel flauschig weiss"),
    (   5875.8, "sd35_large", "Ein Kuenstler der vor einer leeren Leinwand steht mit Pinsel bereit"),
    (   5877.2, "sd35_large", "Pflastersteine auf denen Kreidezeichnungen zu sehen sind bunt und kindlich schoen"),
    (   5877.8, "sd35_large", "Zwei Kinder wandern durch einen Wald mit hohen Baeumen und Sonnenlicht"),
    (   5881.3, "sd35_large", "Ein Stuhl der auf einem Tisch steht in einem leeren Raum beleuchtet"),
    (   5885.9, "sd35_large", "Geometrische Formen die sich ueberlappen auf weissem Hintergrund mit Schatten"),
    (   5886.4, "sd35_large", "Ein Kreis und ein Dreieck die zusammen eine neue Form bilden bunt"),
    (   5886.5, "sd35_large", "Gelbe Blumen auf einer gruenen Wiese mit blauem Himmel und Wolken"),
    (   5886.9, "sd35_large", "Ein Hund der neben einem Kind sitzt auf einer Bank im Park"),
    (   5898.0, "sd35_large", "Abstrakte Linien die sich kreuzen in verschiedenen Farben auf schwarzem Grund"),
    (   5903.2, "sd35_large", "Ein Fenster durch das Sonnenlicht in einen dunklen Raum faellt warm"),
    (   5909.2, "sd35_large", "Haende die ein Blatt Papier halten mit einer Zeichnung darauf klar"),
    (   5913.4, "sd35_large", "Ein roter Apfel auf einem weissen Teller mit einem Messer daneben"),
    (   5916.4, "sd35_large", "Berge im Hintergrund mit einem See davor und Baeumen am Ufer"),
    (   5917.6, "sd35_large", "Ein altes Fahrrad das an einer Mauer lehnt mit Blumen drumherum"),
    (   5920.5, "sd35_large", "Sterne am Nachthimmel ueber einer kleinen Stadt mit beleuchteten Fenstern"),
    (   5948.7, "sd35_large", "Ein Vogel der auf einem Ast sitzt und in die Ferne schaut"),
    (   5949.4, "sd35_large", "Regen der auf eine Fensterscheibe faellt mit verschwommenen Lichtern draussen"),
    (   5951.2, "sd35_large", "Ein Kind das mit Kreide auf den Boden malt bunte Figuren gross"),
    (   5962.4, "sd35_large", "Zwei Haende die ein Herz formen vor einem Sonnenuntergang am Meer"),
    (   5974.4, "sd35_large", "Ein Buch das aufgeschlagen auf einem Holztisch liegt mit Kerze daneben"),
    (   5975.1, "sd35_large", "Bunte Luftballons die in den blauen Himmel steigen ueber einer Stadt"),
    (   5987.6, "sd35_large", "Ein Schmetterling der auf einer roten Blume sitzt im Sonnenlicht warm"),
    (   5994.1, "sd35_large", "Ein Leuchtturm am Meer bei Nacht mit Sternen und Mondschein hell"),
    (   6074.5, "sd35_large", "Alte Treppe die nach oben fuehrt mit Pflanzen an den Seiten"),
    (   6109.0, "sd35_large", "Ein Baum der alleine auf einem Huegel steht bei Sonnenuntergang orange"),
    (   6109.2, "sd35_large", "Schuhe die auf einer nassen Strasse stehen mit Pfuetzen und Regen"),
    (   6111.9, "sd35_large", "Ein Zug der durch eine verschneite Landschaft faehrt mit Bergen hinten"),
    (   6114.1, "sd35_large", "Haende die Ton formen auf einer Toepferscheibe die sich schnell dreht"),
    (   6116.3, "sd35_large", "Ein Spiegel in dem man einen Garten sieht mit bunten Blumen drin"),
    (   6119.2, "sd35_large", "Kinder die zusammen ein grosses Bild malen auf dem Boden kniend"),
    (   6123.2, "sd35_large", "Ein alter Koffer der offen steht mit Postkarten und Fotos darin"),
    (   6126.4, "sd35_large", "Muscheln am Strand mit Wellen die sanft ans Ufer kommen leise"),
    (   6128.6, "sd35_large", "Ein Papierflugzeug das durch einen blauen Himmel mit Wolken fliegt weit"),
    (   6141.1, "sd35_large", "Farben die ineinander verlaufen wie bei einem Aquarell weich und fliessend"),
    (   6141.3, "sd35_large", "Ein Fahrrad mit einem Korb voller Blumen auf einem Feldweg sonnig"),
    (   6142.1, "sd35_large", "Treppen die in verschiedene Richtungen fuehren wie bei Escher surreal verschlungen"),
    (   6146.2, "sd35_large", "Ein Glas Wasser das auf einem Fensterbrett steht mit Licht hindurch"),
    (   6153.5, "sd35_large", "Kinder die im Regen tanzen mit bunten Gummistiefeln und Regenjacken froh"),
    (   6156.6, "sd35_large", "Ein alter Schluessel auf einem Holztisch mit Moos und Blaettern drumherum"),
    (   6158.0, "sd35_large", "Wolken die wie Tiere aussehen an einem blauen Sommerhimmel flauschig weiss"),
    (   6160.3, "sd35_large", "Ein Kuenstler der vor einer leeren Leinwand steht mit Pinsel bereit"),
    (   6228.3, "sd35_large", "Pflastersteine auf denen Kreidezeichnungen zu sehen sind bunt und kindlich schoen"),
    (   6235.3, "sd35_large", "Zwei Kinder wandern durch einen Wald mit hohen Baeumen und Sonnenlicht"),
    (   6243.4, "sd35_large", "Ein Stuhl der auf einem Tisch steht in einem leeren Raum beleuchtet"),
    (   6249.2, "sd35_large", "Geometrische Formen die sich ueberlappen auf weissem Hintergrund mit Schatten"),
    (   7443.2, "sd35_large", "Ein Kreis und ein Dreieck die zusammen eine neue Form bilden bunt"),
    (   7538.1, "sd35_large", "Gelbe Blumen auf einer gruenen Wiese mit blauem Himmel und Wolken"),
    (   7538.5, "sd35_large", "Ein Hund der neben einem Kind sitzt auf einer Bank im Park"),
    (   7622.5, "sd35_large", "Abstrakte Linien die sich kreuzen in verschiedenen Farben auf schwarzem Grund"),
    (   7723.5, "sd35_large", "Ein Fenster durch das Sonnenlicht in einen dunklen Raum faellt warm"),
    (   7885.8, "sd35_large", "Haende die ein Blatt Papier halten mit einer Zeichnung darauf klar"),
]

assert len(WORKSHOP_REQUESTS) == 219, f"Expected 219 requests, got {len(WORKSHOP_REQUESTS)}"


# --- Configs that need img2img input ---
IMG2IMG_CONFIGS = {"qwen_img2img", "flux2_img2img"}


def compute_adjusted_offsets(max_gap: float) -> list[float]:
    """Cap inter-request gaps at max_gap seconds while preserving burst timing."""
    if max_gap <= 0:
        return [offset for offset, _, _ in WORKSHOP_REQUESTS]

    adjusted = [0.0]
    for i in range(1, len(WORKSHOP_REQUESTS)):
        raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
        capped_gap = min(raw_gap, max_gap)
        adjusted.append(adjusted[-1] + capped_gap)
    return adjusted


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
    no_image: bool = False,
    input_image_path: Optional[str] = None,
) -> RequestResult:
    """Send a single generation request via SSE and wait for completion."""
    start = time.monotonic()

    # For img2img without an actual image, fall back to sd35_large (t2i)
    effective_config = config
    if config in IMG2IMG_CONFIGS and (no_image or not input_image_path):
        effective_config = "sd35_large"

    params = {
        "output_config": effective_config,
        "input_text": prompt,
        "prompt": prompt,
        "enable_streaming": "true",
        "device_id": f"loadtest_{index % 11}",  # Simulate 11 devices (workshop had ~11)
    }

    # Add input_image for img2img
    if effective_config in IMG2IMG_CONFIGS and input_image_path:
        params["input_image"] = input_image_path

    url = f"{base_url}/api/schema/pipeline/generation"

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            status = "unknown"
            error = None
            queue_rejected = False
            current_event = ""

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


async def run_simulation(port: int, speed: float, dry_run: bool, no_image: bool, image_path: str, max_gap: float = 0):
    base_url = f"http://localhost:{port}"
    adjusted = compute_adjusted_offsets(max_gap)
    original_duration = WORKSHOP_REQUESTS[-1][0]
    adjusted_duration = adjusted[-1]
    saved = original_duration - adjusted_duration

    print(f"{'='*70}")
    print(f"  Workshop Load Replay — 2026-03-19")
    print(f"  Target: {base_url}")
    print(f"  Speed:  {speed}x")
    print(f"  Max gap: {max_gap}s" + (f"  (saves {saved:.0f}s -> {adjusted_duration/speed:.0f}s at {speed}x)" if max_gap > 0 and saved > 0 else "  (disabled)" if max_gap <= 0 else ""))
    print(f"  Mode:   {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Image:  {'skip (t2i only)' if no_image else f'img2img with {image_path}'}")
    print(f"  Requests: {len(WORKSHOP_REQUESTS)}")
    print(f"{'='*70}")
    print()

    # Config distribution
    from collections import Counter
    configs = Counter(c for _, c, _ in WORKSHOP_REQUESTS)
    print(f"  Config distribution:")
    for cfg, cnt in configs.most_common():
        print(f"    {cfg:30s} {cnt:3d}  ({100*cnt/len(WORKSHOP_REQUESTS):.0f}%)")
    print()

    if dry_run:
        print("Timing preview (no requests sent):")
        for i, ((_offset, config, prompt), adj_offset) in enumerate(zip(WORKSHOP_REQUESTS, adjusted)):
            t = adj_offset / speed
            gap_orig = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0] if i > 0 else 0
            gap_adj = adjusted[i] - adjusted[i - 1] if i > 0 else 0
            capped = " (capped)" if gap_orig != gap_adj else ""
            print(f"  T+{t:7.1f}s  {config:25s}  {prompt[:40]}{capped}")
        print(f"\nOriginal duration: {original_duration/speed:.0f}s  |  Adjusted: {adjusted_duration/speed:.0f}s  |  Saved: {saved/speed:.0f}s")
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

    # Upload test image for img2img
    input_image_ref = None
    if not no_image:
        async with aiohttp.ClientSession() as session:
            input_image_ref = await upload_test_image(session, base_url, image_path)
            if not input_image_ref:
                print("  Falling back to t2i only (no image uploaded)")
                no_image = True

    print(f"Starting replay...\n")

    results: list[RequestResult] = []
    tasks: list[asyncio.Task] = []
    sim_start = time.monotonic()

    async with aiohttp.ClientSession() as session:
        for i, ((_offset, config, prompt), adj_offset) in enumerate(zip(WORKSHOP_REQUESTS, adjusted)):
            # Wait until the right moment (using adjusted offsets with gap capping)
            target_time = adj_offset / speed
            now = time.monotonic() - sim_start
            wait = target_time - now
            if wait > 0:
                await asyncio.sleep(wait)

            elapsed = time.monotonic() - sim_start
            print(f"[T+{elapsed:7.1f}s] #{i+1:3d} SEND  {config:25s}  {prompt[:50]}")

            # Fire and forget (concurrent, like real devices)
            task = asyncio.create_task(
                send_request(session, base_url, i, config, prompt, no_image, input_image_ref)
            )
            tasks.append(task)

        # Wait for all to complete
        print(f"\n--- All {len(tasks)} requests sent, waiting for responses... ---\n")
        results = await asyncio.gather(*tasks)

    # --- Report ---
    total_time = time.monotonic() - sim_start
    print(f"\n{'='*70}")
    print(f"  RESULTS — Workshop 2026-03-19 Replay")
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
        cfg_blocked = sum(1 for r in cfg_list if r.status == "blocked")
        cfg_errors = sum(1 for r in cfg_list if r.status == "error")
        cfg_durations = [r.duration_ms for r in cfg_list if r.status == "success"]
        avg_s = f"{sum(cfg_durations)/len(cfg_durations)/1000:.1f}s" if cfg_durations else "-"
        print(f"    {cfg:25s}  {cfg_success}/{len(cfg_list)} success  blocked={cfg_blocked}  errors={cfg_errors}  avg={avg_s}")
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

    if blocked:
        print(f"  Blocked details:")
        for r in blocked:
            print(f"    #{r.index+1:3d} {r.config:25s} {r.duration_ms/1000:.1f}s  {r.error}")
        print()

    if timeouts:
        print(f"  Timeout details:")
        for r in timeouts:
            print(f"    #{r.index+1:3d} {r.config:25s} {r.duration_ms/1000:.0f}s  {r.error}")
        print()

    # Compare with workshop baseline
    print(f"  Workshop baseline comparison:")
    print(f"    19.03. production: 219 requests, ~97% success (all SD3.5-dominant)")
    print(f"    20.03. production: 107 requests, 97.2% success (sd35 + qwen mixed)")
    print(f"    This replay:       {len(results)} requests, {100*len(success)/len(results):.0f}% success")
    print()


def main():
    parser = argparse.ArgumentParser(description="Workshop Load Replay — 2026-03-19")
    parser.add_argument("--port", type=int, default=17802, help="Backend port (default: 17802)")
    parser.add_argument("--fast", action="store_true", help="4x speed")
    parser.add_argument("--dry-run", action="store_true", help="Print timing only, no requests")
    parser.add_argument("--no-image", action="store_true", help="Skip img2img, use sd35_large fallback")
    parser.add_argument("--speed", type=float, default=None, help="Custom speed multiplier")
    parser.add_argument("--image", type=str, default="/home/joerissen/Pictures/dubestimmst1.png",
                        help="Test image for img2img (default: dubestimmst1.png)")
    parser.add_argument("--max-gap", type=float, default=15.0,
                        help="Cap idle gaps between requests in seconds (default: 15, 0=no cap)")
    args = parser.parse_args()

    speed = args.speed or (4.0 if args.fast else 1.0)
    asyncio.run(run_simulation(args.port, speed, args.dry_run, args.no_image, args.image, args.max_gap))


if __name__ == "__main__":
    main()
