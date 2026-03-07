#!/usr/bin/env python3
"""
Workshop Load Replay — 2026-03-06

Replays the 119 Stage-4 generations from the second kids workshop with
the original timing pattern. 2.7x higher load than 05.03, full media
diversity (SD3.5, Wan2.1 Video, LTX Video, ACEnet Audio, Qwen img2img).

Extracted from: Teilprotokoll 6 3 2026 backend.txt
Prompts are synthetic but realistic length (load pattern is what matters).

Usage:
    python simulate_workshop_260306.py [--port 17802] [--fast] [--dry-run] [--max-gap 15]

    --port PORT       Backend port (default: 17802 = development)
    --fast            Run at 4x speed
    --dry-run         Print timing without sending requests
    --no-image        Skip img2img (use qwen_2511_multi fallback)
    --max-gap SECONDS Cap inter-request idle gaps (default: 15s, 0=no cap)

HOW THIS SCRIPT WAS CREATED (for future sessions creating similar scripts):
    1. Parse the backend log for [STAGE4-GEN] lines to get timestamps + output_configs:
       grep "[STAGE4-GEN] Executing generation with config" backend.txt
    2. Compute offsets from first timestamp
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


# --- Workshop replay data (extracted from backend log 2026-03-06) ---
# Format: (seconds_offset_from_start, output_config, german_prompt)
# Offset 0 = 14:34:51 (first Stage 4 generation)
# 119 entries = all requests that reached Stage 4
# Prompts are synthetic — only timing + config distribution matters

WORKSHOP_REQUESTS = [
    (     0.0, "qwen_2511_multi", "Zeichne ein rotes Viereck auf weissem Hintergrund mit einem kleinen Schatten"),
    (  2842.6, "sd35_large", "Zeichne ein Viereck das aussieht wie aus Holz geschnitzt auf einem Tisch"),
    (  2845.8, "sd35_large", "Forme einen Wuerfel der auf einer Seite steht mit bunten Seiten"),
    (  2866.3, "sd35_large", "Ein grosser Kreis der wie eine Seifenblase schimmert in Regenbogenfarben"),
    (  2868.8, "sd35_large", "Zeichne einen Kreis der aussieht wie ein Planet mit Ringen im Weltraum"),
    (  2884.4, "sd35_large", "Forme einen Wuerfel aus Glas durch den man hindurchsehen kann"),
    (  2898.9, "sd35_large", "Ein Viereck das wie ein Fenster aussieht mit Blick auf einen Garten"),
    (  2994.7, "sd35_large", "Zeichne einen Kreis der wie eine alte Muenze aussieht mit Muster drauf"),
    (  2996.0, "sd35_large", "Ein riesiger Wuerfel aus Eis der in der Sonne langsam schmilzt"),
    (  3355.8, "sd35_large", "Rote Drache mit drei Koepfen und zwei Schwaenzen der ueber Berge fliegt"),
    (  3463.0, "sd35_large", "Eine Pyramide die in der Wueste steht mit Kamelen davor und Sonnenuntergang"),
    (  3466.1, "sd35_large", "Ein blauer Kreis der wie ein See aussieht mit Spiegelung darin"),
    (  3574.5, "sd35_large", "Eine grosse Pyramide mit glatten Steinbloecken und Sand drumherum"),
    (  3575.3, "sd35_large", "Ein perfekter Kreis gezeichnet mit Bleistift auf weissem Papier"),
    (  3594.9, "sd35_large", "Stern in einem Kreis auf einer weissen Wand mit blauem Hintergrund"),
    (  3661.7, "sd35_large", "Geometrischer blauer Kreis mit einer Linie durch die Mitte ganz genau"),
    (  3707.8, "sd35_large", "Ein Wuerfel der in der Luft schwebt mit einem Schatten auf dem Boden"),
    (  3770.6, "wan22_t2v_video_fast", "Ein Kreis wird langsam auf ein Blatt Papier gezeichnet mit einem Bleistift"),
    (  3838.5, "sd35_large", "Ein schwarzer isometrischer Wuerfel auf weissem Papier mit geraden Kanten"),
    (  3913.7, "ltx_video", "Die Kamera faehrt langsam ueber eine rote Wueste mit einem Fahrzeug im Vordergrund"),
    (  3954.5, "wan22_t2v_video_fast", "Ein Roboter laeuft durch einen Wald und sammelt Blaetter vom Boden auf"),
    (  3983.1, "sd35_large", "Ein Drache mit roten Schuppen der auf einem Burgturm sitzt und Feuer spuckt"),
    (  4024.6, "sd35_large", "Eine alte Burg auf einem Berg mit Wolken und einem Regenbogen darueber"),
    (  4050.6, "sd35_large", "Ein Roboter der in einer Blumenwiese steht und eine Blume anschaut"),
    (  4082.6, "sd35_large", "Unterwasserwelt mit bunten Fischen und Korallen und Sonnenstrahlen von oben"),
    (  4758.5, "sd35_large", "Ein grosser Elefant der an einem Wasserloch steht bei Sonnenuntergang in Afrika"),
    (  5954.4, "sd35_large", "Nordlichter ueber einem stillen See mit Bergen im Hintergrund und Sternen"),
    (  6248.4, "sd35_large", "Ein Segelschiff auf dem Meer bei Sturm mit hohen Wellen und dunklen Wolken"),
    (  6250.1, "sd35_large", "Japanischer Garten im Fruehling mit Kirschblueten und einer kleinen Bruecke"),
    (  6408.4, "sd35_large", "Ein alter Leuchtturm am Meer bei Nacht mit Sternen und Mondschein"),
    (  6445.5, "sd35_large", "Heisse Wueste mit einer Oase in der Mitte und Palmen und klarem Wasser"),
    (  6621.4, "sd35_large", "Ein Adler der ueber schneebedeckte Berge fliegt mit ausgebreiteten Fluegeln"),
    (  6953.8, "qwen_img2img", "Mach die Farben kraeftiger und den Hintergrund etwas dunkler bitte"),
    (  7219.3, "sd35_large", "Ein Pferd das am Strand galoppiert mit Wellen und Sonnenuntergang dahinter"),
    (  7231.7, "qwen_2511_multi", "Zeichne einen Kreis der wie eine Sonne aussieht mit Strahlen drumherum"),
    (  7257.3, "qwen_2511_multi", "Forme einen Wuerfel der aussieht wie ein Geschenk mit einer Schleife oben"),
    (  7269.9, "qwen_2511_multi", "Zeichne ein Viereck das wie ein Bilderrahmen aussieht mit einem Bild drin"),
    (  7294.3, "qwen_2511_multi", "Ein Dreieck das wie ein Berg aussieht mit Schnee auf der Spitze"),
    (  7299.4, "wan22_t2v_video_fast", "Ein Ball rollt langsam einen gruenen Huegel hinunter ins Tal"),
    (  7318.2, "qwen_2511_multi", "Sterne am Nachthimmel mit einer Sternschnuppe die ueber den Himmel zieht"),
    (  7378.6, "qwen_2511_multi", "Ein grosses Herz aus roten und rosa Blumen auf einer gruenen Wiese"),
    (  7394.0, "qwen_2511_multi", "Bunte Kreise und Quadrate die zusammen ein Muster bilden wie ein Mosaik"),
    (  7399.7, "qwen_img2img", "Mehr Kontrast bitte und die Schatten sollen etwas weicher sein"),
    (  7407.8, "wan22_t2v_video_fast", "Wasser fliesst einen hohen Wasserfall hinunter in einen See mit Nebel"),
    (  7428.7, "qwen_2511_multi", "Ein kleines Haus mit einem Garten voller Blumen und einem Zaun davor"),
    (  7588.1, "wan22_t2v_video_fast", "Wolken ziehen langsam ueber einen blauen Himmel mit Sonnenstrahlen"),
    (  7698.2, "wan22_t2v_video_fast", "Blumen oeffnen sich langsam im Zeitraffer auf einer gruenen Wiese"),
    (  7759.9, "qwen_img2img", "Der Hintergrund soll blau sein wie der Himmel an einem klaren Tag"),
    (  7849.2, "qwen_img2img", "Mach das ganze Bild so als waere es mit Wasserfarben gemalt worden"),
    (  7851.4, "qwen_img2img", "Fuege einen grossen Regenbogen am Himmel hinzu ueber den Bergen"),
    (  7943.1, "sd35_large", "Ein Delphin der aus dem blauen Wasser springt mit Spritzern und Sonnenlicht"),
    (  7949.8, "qwen_img2img", "Die Sonne soll untergehen und alles in warmes oranges Licht tauchen"),
    (  8031.7, "sd35_large", "Ein stiller Bergsee bei Sonnenaufgang mit Nebel ueber dem Wasser"),
    (  8097.4, "wan22_t2v_video_fast", "Ein grosser Vogel fliegt langsam ueber das blaue Meer bei Sonnenuntergang"),
    (  8146.9, "sd35_large", "Polarlichter in Gruen und Lila ueber weissen Eisbergen in der Nacht"),
    (  8243.9, "sd35_large", "Ein dichter Wald im Nebel mit Sonnenstrahlen die durch die Baeume fallen"),
    (  8625.4, "qwen_img2img", "Mach den Himmel dramatischer mit mehr Wolken und tieferen Farben"),
    (  8711.7, "qwen_img2img", "Fuege viele kleine Sterne am Nachthimmel hinzu wie eine Galaxie"),
    (  8735.6, "wan22_t2v_video_fast", "Flammen tanzen langsam in einem alten Kamin mit Funken die aufsteigen"),
    (  8736.4, "wan22_t2v_video_fast", "Schneeflocken fallen ganz langsam vom Himmel auf einen Tannenwald"),
    (  8742.7, "sd35_large", "Ein Samurai der unter rosa Kirschblueten steht mit einem Schwert"),
    (  8743.4, "sd35_large", "Eine Hoehle voller leuchtender Kristalle in verschiedenen Farben"),
    (  8744.1, "sd35_large", "Ein grosser Drache der auf einem Burgturm sitzt und in die Ferne schaut"),
    (  8744.7, "sd35_large", "Eine Mondlandschaft mit Kratern und der Erde am Horizont im Weltraum"),
    (  8745.2, "sd35_large", "Ein kleiner Kolibri der vor einer roten Bluete schwebt mit schnellen Fluegeln"),
    (  8745.3, "sd35_large", "Eine alte Bibliothek mit hohen Regalen voller Buecher und Kerzen auf dem Tisch"),
    (  8747.8, "sd35_large", "Ein altes Segelschiff im Sturm auf hohen Wellen mit Blitzen am Himmel"),
    (  8754.9, "sd35_large", "Ein japanischer Garten im Fruehling mit einem Teich und roten Ahornblaettern"),
    (  8755.7, "sd35_large", "Ein grosser Elefant der am Wasserloch steht bei Sonnenuntergang in der Savanne"),
    (  8764.7, "sd35_large", "Ein Steampunk Uhrwerk mit Zahnraedern und Dampf und goldenem Metall"),
    (  8767.5, "sd35_large", "Ein Wolf der auf einem Felsen steht und den Vollmond anheult bei Nacht"),
    (  8767.6, "sd35_large", "Eine antike griechische Tempelruine mit Saeulen und Marmorstufen"),
    (  8774.1, "sd35_large", "Ein Phoenixvogel der aus Flammen aufsteigt mit goldenen und roten Federn"),
    (  8985.9, "wan22_t2v_video_fast", "Eine einzelne Kerze flackert langsam im Wind in einem dunklen Raum"),
    (  8985.9, "wan22_t2v_video_fast", "Wellen brechen langsam am Strand und das Wasser zieht sich zurueck"),
    (  8990.5, "wan22_t2v_video_fast", "Ein einzelnes Blatt faellt langsam von einem hohen Baum im Herbst"),
    (  9001.5, "qwen_img2img", "Mach alles so als waere es Nacht mit Sternen und Mondschein bitte"),
    (  9065.3, "sd35_large", "Ein Oktopus in der Tiefsee der mit seinen Armen durch Korallen schwimmt"),
    (  9065.4, "sd35_large", "Ein Wikinger Langschiff das ueber das Meer segelt mit einem Drachenkopf vorne"),
    (  9065.4, "sd35_large", "Ein buntes Chamaeleon das auf einem gruenen Ast sitzt im Regenwald"),
    (  9065.7, "sd35_large", "Eine mittelalterliche Burganlage mit Tuermen und einer Zugbruecke und Wassergraben"),
    (  9066.3, "sd35_large", "Ein Pfau der sein buntes Rad schlaegt auf einer gruenen Wiese im Sonnenlicht"),
    (  9147.1, "qwen_img2img", "Der Kontrast soll staerker sein damit man die Details besser sieht"),
    (  9258.9, "qwen_img2img", "Fuege ein paar grosse weisse Wolken am blauen Himmel hinzu bitte"),
    (  9301.5, "qwen_img2img", "Mach das ganze Bild bunter und froehlicher mit mehr Farben ueberall"),
    (  9303.1, "sd35_large", "Aurora Borealis in Gruen und Blau ueber einem norwegischen Fjord bei Nacht"),
    (  9323.7, "sd35_large", "Ein Gepard der durch die goldene Savanne rennt mit Staub hinter sich"),
    (  9328.2, "sd35_large", "Eine versunkene Stadt unter dem Meer mit alten Gebaeuden und Fischen"),
    (  9342.1, "sd35_large", "Hunderte Leuchtkaefer im dunklen Wald die zwischen den Baeumen leuchten"),
    (  9371.8, "sd35_large", "Ein Vulkan der bei Nacht ausbricht mit roter Lava die den Berg herunterfliesst"),
    (  9373.6, "sd35_large", "Ein weisses Einhorn das im Mondlicht auf einer Wiese steht mit Sternen"),
    (  9385.5, "qwen_img2img", "Mehr Details im Vordergrund bitte und die Textur soll schaerfer sein"),
    (  9414.3, "sd35_large", "Ein Korallenriff von oben gesehen mit bunten Fischen und klarem Wasser"),
    (  9448.6, "qwen_img2img", "Mach den Hintergrund unscharf damit das Hauptmotiv besser rauskommt"),
    (  9470.1, "sd35_large", "Ein grosses Baumhaus im tropischen Regenwald mit Leitern und Lichtern"),
    (  9471.3, "sd35_large", "Ein Sternennebel in Lila und Blau mit leuchtenden Sternen im Weltraum"),
    (  9487.4, "sd35_large", "Ein Fuchs der durch buntes Herbstlaub auf dem Waldboden laeuft"),
    (  9493.9, "sd35_large", "Ein kristallklarer Bergsee umgeben von hohen Bergen mit Schnee auf den Gipfeln"),
    (  9501.9, "sd35_large", "Ein freundlicher Roboter der in einer bunten Blumenwiese steht und winkt"),
    (  9510.0, "sd35_large", "Eine alte Windmuehle auf einem Huegel bei Sonnenuntergang mit goldenem Licht"),
    (  9510.1, "qwen_img2img", "Es soll schneien, ueberall sollen Schneeflocken fallen und alles weiss sein"),
    (  9534.9, "sd35_large", "Ein riesiger Blauwal der langsam aus dem dunklen Meer auftaucht"),
    (  9534.9, "sd35_large", "Ein Lavastrom der ins blaue Meer fliesst mit Dampf und roten Steinen"),
    (  9536.0, "sd35_large", "Ein Eisbaer der auf einer Eisscholle steht mit dem Polarmeer drumherum"),
    (  9536.6, "sd35_large", "Buntes Feuerwerk ueber einer Stadt bei Nacht mit Spiegelung im Fluss"),
    (  9541.9, "sd35_large", "Ein Adlerhorst hoch oben auf einem steilen Felsen mit weitem Blick ins Tal"),
    (  9545.2, "sd35_large", "Ein tropischer Wasserfall der in einen tuerkisblauen Pool faellt im Dschungel"),
    (  9549.8, "sd35_large", "Ein weisser Schwan der elegant auf einem stillen See schwimmt bei Daemmerung"),
    (  9550.0, "sd35_large", "Dunkle Gewitterwolken ueber einem goldenen Weizenfeld kurz vor dem Regen"),
    (  9558.9, "sd35_large", "Ein buntes Chamaeleon das gerade seine Farbe wechselt auf einem tropischen Blatt"),
    (  9572.6, "qwen_img2img", "Der Himmel soll lila und pink sein wie bei einem dramatischen Sonnenuntergang"),
    (  9697.5, "acenet_t2instrumental", "Sanfte Klaviermelodie mit leichtem Regen im Hintergrund, ruhig und entspannend"),
    (  9799.4, "wan22_t2v_video_fast", "Ein kleiner Vogel der von Ast zu Ast huepft in einem verschneiten Winterwald"),
    ( 10595.4, "sd35_large", "Ein schlafender Drache der auf einem Berg aus Gold und Edelsteinen liegt"),
    ( 10906.9, "wan22_t2v_video_fast", "Gruene und blaue Nordlichter die langsam am dunklen Nachthimmel tanzen"),
    ( 11057.4, "wan22_t2v_video_fast", "Ein bunter Schmetterling der langsam durch ein Feld voller Wildblumen fliegt"),
    ( 11058.2, "wan22_t2v_video_fast", "Regentropfen fallen auf ein grosses gruenes Blatt und rollen langsam herunter"),
    ( 11222.4, "wan22_t2v_video_fast", "Sand rieselt langsam durch eine alte Sanduhr aus Holz und Glas"),
    ( 11301.5, "wan22_t2v_video_fast", "Ein roter Zug faehrt langsam durch eine verschneite Winterlandschaft mit Bergen"),
]

assert len(WORKSHOP_REQUESTS) == 119, f"Expected 119 requests, got {len(WORKSHOP_REQUESTS)}"


# --- Configs that need img2img input ---
IMG2IMG_CONFIGS = {"qwen_img2img", "qwen_2511_multi", "flux2_img2img"}


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
    import os
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
        "device_id": f"loadtest_{index % 9}",  # Simulate 9 iPads
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


async def run_simulation(port: int, speed: float, dry_run: bool, no_image: bool, image_path: str, max_gap: float = 0):
    base_url = f"http://localhost:{port}"
    adjusted = compute_adjusted_offsets(max_gap)
    original_duration = WORKSHOP_REQUESTS[-1][0]
    adjusted_duration = adjusted[-1]
    saved = original_duration - adjusted_duration

    print(f"{'='*70}")
    print(f"  Workshop Load Replay — 2026-03-06")
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
        print(f"    {cfg:30s} {cnt:3d}")
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
            print(f"[T+{elapsed:7.1f}s] #{i+1:3d} SEND  {config:25s}  {prompt[:40]}")

            # Fire and forget (concurrent, like real iPads)
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
    from collections import Counter
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

    # Compare with workshop baseline
    print(f"  Workshop baseline (2026-03-06):")
    print(f"    Success rate: 76%    (this run: {100*len(success)/len(results):.0f}%)")
    print(f"    Mistral 503:  5.6%   (this run: see errors above)")
    print(f"    Ollama TO:    7%     (this run: {100*len(timeouts)/len(results):.0f}%)")
    print(f"    Safety blocks: 7.7%  (this run: {100*len(blocked)/len(results):.0f}%)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Workshop Load Replay — 2026-03-06")
    parser.add_argument("--port", type=int, default=17802, help="Backend port (default: 17802)")
    parser.add_argument("--fast", action="store_true", help="4x speed")
    parser.add_argument("--dry-run", action="store_true", help="Print timing only, no requests")
    parser.add_argument("--no-image", action="store_true", help="Skip img2img, use qwen_2511_multi fallback")
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
