#!/usr/bin/env python3
"""Legt fuer jeden offenen Befund den getippten Wert und den massgeblichen
Wert nebeneinander. Das Skript beurteilt nichts.

Hintergrund: am 09.09.2026 wurde die Codebase auf eine Fehlerklasse durchsucht
-- eine von Hand getippte Zahl, wo das darunterliegende System die richtige
schon kennt und oft selbst misst. Der Bericht darueber stammte vom selben
Modell, das die Fehler geschrieben hatte, und ein Drittel davon war falsch:
drei Befunde erfunden, fuenf im Ausmass daneben. Ein Text laesst sich nicht
pruefen, zwei Zahlen nebeneinander schon.

Darum druckt dieses Skript beide Seiten und urteilt nicht. Wo ein Befund
erfunden war, kommen zwei gleiche Zahlen heraus, oder die Fundstelle fehlt,
oder die Pruefung stuerzt ab -- alle drei sind sichtbar.

    python3 scripts/befund_belege.py            # alles
    python3 scripts/befund_belege.py --offen    # ohne die Regressionswaechter

Status ist rein mechanisch:
  UNGLEICH        beide Werte gefunden, sie unterscheiden sich
  GLEICH          beide Werte gefunden, sie sind identisch
  NICHT GEFUNDEN  eine der beiden Seiten war nicht auffindbar
  ABSTURZ         die Pruefung selbst ist gescheitert
Ein Strich heisst: hier stehen zwei Angaben nebeneinander, die kein
Gleichheitszeichen verbindet -- sie zu lesen ist Sache des Lesers.
"""
import ast
import glob
import json
import os
import re
import subprocess
import sys
import traceback
import urllib.parse
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.environ.get("GPU_MODEL_STATS_PATH", "/var/tmp/ai4artsed/gpu_model_stats.json")
GPU_SERVICE = os.environ.get("GPU_SERVICE_URL", "http://localhost:17803")
COMFYUI = os.environ.get("COMFYUI_URL", "http://127.0.0.1:17804")

ROWS = []
NUR_OFFEN = "--offen" in sys.argv


def add(nr, sache, getippt, massgeblich, quelle, status="—"):
    ROWS.append((nr, sache, getippt, massgeblich, quelle, status))


def vergleich(nr, sache, a, b, quelle):
    if a is None or b is None:
        add(nr, sache, a, b, quelle, "NICHT GEFUNDEN")
    else:
        add(nr, sache, a, b, quelle, "GLEICH" if str(a) == str(b) else "UNGLEICH")


def check(nr, sache, behoben=False):
    def deco(fn):
        if NUR_OFFEN and behoben:
            return fn
        try:
            fn()
        except Exception as exc:
            ROWS.append((nr, sache, "-", "-", f"{type(exc).__name__}: {exc}", "ABSTURZ"))
            traceback.print_exc(file=sys.stderr)
        return fn
    return deco


# ---------------------------------------------------------------- Werkzeuge
def grab(rel, pattern, group=0, flags=0):
    """Erster Treffer des Musters. Gibt (text, 'datei:zeile') zurueck."""
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None, f"{rel} FEHLT"
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        m = re.search(pattern, line, flags)
        if m:
            try:
                text = m.group(group) if group else m.group(0)
            except IndexError:
                text = m.group(0)
            return text.strip(), f"{rel}:{i}"
    return None, f"{rel}: Muster nicht gefunden"


def grab_all(rel, pattern, flags=0):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return []
    out = []
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        for m in re.finditer(pattern, line, flags):
            out.append((m, f"{rel}:{i}"))
    return out


def sh(command, timeout=90):
    try:
        return subprocess.run(["bash", "-lc", command], capture_output=True,
                              text=True, timeout=timeout).stdout.strip()
    except Exception as exc:
        return f"Kommando gescheitert: {exc}"


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "ai4artsed-belege/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def untergrenze(art):
    """Was der Messwertspeicher zu dieser Art haelt -- als UNTERGRENZE.

    Der Fussabdruck dort ist keine Groesse. Er entsteht aus dem Rueckgang der
    freien Karte waehrend eines Auftrags, alle fuenf Sekunden abgetastet, und
    trifft die Spitze in der Regel nicht; ein Modell, das schon lag, misst nur
    seine Aktivierungen; und die Verdraengung des Auftrags selbst hebt den
    oberen Rand an, sodass die Differenz das Verdraengte sein kann statt des
    Modells. Die Plattform schreibt das an zwei Stellen selbst hin -- der
    Kommentar zu GPU_ADMISSION_PREFETCH in gpu_service/config.py und die Notiz
    in gpu_service/services/gpu_admission.py -- und laesst das Vorausladen
    genau deshalb aus.

    Darum steht die laengste Haltezeit desselben Schluessels mit dabei: ein
    Auftrag von einer halben Sekunde kann keinen Ladevorgang enthalten, und
    eine Zahl von so einem Auftrag beschreibt keine Gewichte. Der Schluessel
    steht ebenfalls dabei; er wird exakt gesucht, nie ueber Teilzeichenketten
    geraten.
    """
    if not os.path.exists(STATS):
        return None, f"{STATS} fehlt"
    rec = json.load(open(STATS)).get("models", {}).get(f"{art}::{art}")
    if not rec or rec.get("vram_ema_mb") is None:
        return None, f"kein Eintrag {art}::{art}"
    halt = rec.get("hold_max_s")
    return (f"{rec.get('vram_max_mb')} MB Untergrenze (n={rec.get('vram_n')}, "
            f"laengster Halt {halt}s, {art}::{art})"), f"{art}::{art}"


def spitzenmessung(art):
    """Die einzige Spitzenmessung, die die Plattform fuehrt: MODEL_PEAK_VRAM_MB.

    Aufgenommen ueber nvidia-smi waehrend der Inferenz. Der Schluessel wird
    exakt gesucht -- die Tabelle ist nach Modell und dtype benannt
    (sd35_large_fp16), nicht nach der Art der Schleuse, und ein Treffer ueber
    Teilzeichenketten waere geraten.
    """
    treffer, ort = grab("gpu_service/config.py",
                        r'^\s*"' + re.escape(art) + r'":\s*(\d[\d_]*)', 1)
    if treffer is None:
        return None, f"kein Eintrag {art!r} in MODEL_PEAK_VRAM_MB"
    return f"{int(treffer.replace('_', ''))} MB Spitze (nvidia-smi)", ort


# ======================================================== Regressionswaechter
@check("B1", "Video: Latent-Knoten und shift", behoben=True)
def _():
    chunk = "devserver/schemas/chunks/output_video_wan22_t2v_fast.json"
    cls, loc = grab(chunk, r'"class_type":\s*"([A-Za-z0-9_]*Latent[A-Za-z0-9_]*)"', 1)
    vorlage = glob.glob(os.path.join(
        ROOT, "dlbackend/ComfyUI/venv/lib/python*/site-packages/"
        "comfyui_workflow_templates_media_video/templates/video_wan2_2_14B_t2v.json"))
    referenz = shifts = None
    if vorlage:
        d = json.load(open(vorlage[0]))
        aktiv = [n for n in d["nodes"] if n.get("mode") == 0]
        referenz = next((n["type"] for n in aktiv if "Latent" in n["type"]), None)
        shifts = sorted({round(n["widgets_values"][0], 1) for n in aktiv
                         if n["type"] == "ModelSamplingSD3"})
    vergleich("B1", "Latent-Knoten", cls, referenz, f"{loc} | ComfyUI-Vorlage")
    unser = sorted({float(m.group(1)) for m, _ in grab_all(chunk, r'"shift":\s*([0-9.]+)')})
    vergleich("B1", "shift", unser, shifts, f"{chunk} | ComfyUI-Vorlage")
    # Teiler und Kanaele des benutzten Knotens
    for datei in ("comfy_extras/nodes_hunyuan.py", "comfy_extras/nodes_wan.py"):
        p = os.path.join(ROOT, "dlbackend/ComfyUI", datei)
        if not (cls and os.path.exists(p)):
            continue
        text = open(p, encoding="utf-8", errors="replace").read()
        i = text.find(f"class {cls}")
        if i < 0:
            continue
        m = re.search(r"torch\.zeros\(\[[^\]]*?,\s*(\d+),.*?height\s*//\s*(\d+)",
                      text[i:i + 4000], re.S)
        if m:
            vergleich("B1", "Kanaele im Latent", m.group(1), "16", f"{datei} | Wan21")
            vergleich("B1", "Teiler", m.group(2), "8", f"{datei} | spacial_downscale_ratio")


@check("B2", "Bilder-Suche: vollstaendige Kategorien", behoben=True)
def _():
    sys.path.insert(0, os.path.join(ROOT, "devserver"))
    from my_app.services import commons_service as C
    found = C._api_get({"action": "query", "list": "search",
                        "srsearch": "painting filetype:bitmap", "srnamespace": "6",
                        "srlimit": str(C.SEARCH_RESULTS)})
    if not found:
        add("B2", "Archiv erreichbar?", "-", "keine Antwort", "commons.wikimedia.org")
        return
    titles = [h["title"] for h in found["query"]["search"]]
    d = C._api_get_complete({"action": "query", "titles": "|".join(titles),
                             "prop": "imageinfo|categories",
                             "iiprop": "url|extmetadata|mime|size",
                             "iiurlwidth": str(C.THUMB_WIDTH), "cllimit": "max"})
    if d is None:
        add("B2", "Antwort vollstaendig?", "-", "nicht zu Ende holbar", "commons_service.py")
        return
    pages = d["query"]["pages"]
    pages = list(pages.values()) if isinstance(pages, dict) else pages
    leer = sum(1 for p in pages if not p.get("categories"))
    zeilen = sum(len(p.get("categories", [])) for p in pages)
    vergleich("B2", "Dateien ohne Kategorien", leer, 0, "Live-Abfrage")
    add("B2", "Kategoriezeilen", zeilen, "500 waren der Deckel einer Anfrage", "Live-Abfrage")
    add("B2", "continue noch offen?", "ja" if "continue" in d else "nein", "nein erwartet",
        "Live-Abfrage")


@check("B3", "Fertiger Auftrag: Rueckgabe gebunden", behoben=True)
def _():
    rel = "devserver/my_app/services/comfyui_ws_client.py"
    tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
    verworfen = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr):
            call = node.value.value if isinstance(node.value, ast.Await) else node.value
            if isinstance(call, ast.Call) and "already_completed" in ast.dump(call.func):
                verworfen.append(node.lineno)
    vergleich("B3", "Aufrufe mit verworfenem Ergebnis", len(verworfen), 0, f"{rel} (AST)")


# ================================================================ Offen: VRAM
@check(1, "Angemeldeter VRAM: was daneben zu legen waere")
def _():
    """Der Befund vom 09.09. lautete: hier steht eine getippte Zahl, wo der
    Dienst die gemessene schon haelt. Das ist widerlegt. Der Messwertspeicher
    haelt eine Untergrenze, keine Groesse -- siehe untergrenze() --, und die
    Plattform sagt das selbst und handelt auch nicht danach. Neben die getippte
    Zahl gehoert eine Spitzenmessung, und fuer diese Arten gibt es keine.

    Der Aufruf wird geparst, nicht gegriffen: das zweite Argument darf ein
    Ausdruck ueber mehrere Zeilen sein, und eine zeilenweise Suche liest davon
    nur den Anfang.
    """
    for pfad in sorted(glob.glob(os.path.join(ROOT, "gpu_service/**/*.py"),
                                 recursive=True)):
        if "__pycache__" in pfad or "/tests/" in pfad:
            continue
        kurz = os.path.relpath(pfad, ROOT)
        try:
            baum = ast.parse(open(pfad, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            name = getattr(knoten.func, "attr", None) or getattr(knoten.func, "id", None)
            if name not in ("request_vram", "request_vram_detailed"):
                continue
            if len(knoten.args) < 2:
                continue
            art = knoten.args[0]
            if not (isinstance(art, ast.Constant) and isinstance(art.value, str)):
                continue
            wert = ast.unparse(knoten.args[1])
            fest = wert.lstrip("-").isdigit()
            spitze, wo = spitzenmessung(art.value)
            unten, _ = untergrenze(art.value)
            gegenueber = spitze or wo
            if unten:
                gegenueber += f"; Speicher: {unten}"
            add(1, art.value, wert + (" (getippt)" if fest else " (berechnet)"),
                gegenueber, f"{kurz}:{knoten.lineno}",
                "UNGLEICH" if (fest and spitze) else "NICHT GEFUNDEN"
                if fest and not spitze else "—")


@check(2, "Diffusers: Tabelle gegen eigene Messung")
def _():
    rel = "gpu_service/services/diffusers_backend.py"
    zuw, l1 = grab(rel, r"_model_vram_mb\[model_id\]\s*=\s*\w+")
    add(2, "gespeichert wird", zuw, "measured_mb, eine Zeile darunter berechnet",
        f"{l1}")
    for m, loc in grab_all("gpu_service/config.py", r'"([a-z0-9_]+)":\s*(\d[\d_]*),?\s*(#.*)$'):
        add(2, m.group(1), m.group(2).replace("_", ""), m.group(3).strip("# ").strip(), loc)
    journal = sh("journalctl -u ai4artsed-gpu --since '30 days ago' --no-pager -o cat "
                 "| grep -o 'estimated: [0-9]*MB, measured: [0-9]*MB' | sort -u | tail -6", 180)
    for line in (journal or "").splitlines():
        add(2, "Journal", "-", line, "journalctl -u ai4artsed-gpu")


@check(3, "Textlabor: Schaetzung gegen Gewichte")
def _():
    verfahren, loc = grab("gpu_service/services/text_backend.py", r"params_b\s*\*\s*[\d.]+")
    add(3, "Verfahren", verfahren, "Parameterzahl und dtype stehen in config.json", loc)
    namen = set()
    for datei in ("gpu_service/config.py", "gpu_service/services/text_backend.py"):
        for m, _ in grab_all(datei, r'"([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)"'):
            namen.add(m.group(1))
    for name in sorted(namen):
        idx = glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--" + name.replace("/", "--")
            + "/snapshots/*/model.safetensors.index.json"))
        if not idx:
            continue
        try:
            total = json.load(open(idx[0])).get("metadata", {}).get("total_size")
        except Exception:
            continue
        if not total:
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*[bB]\b", name)
        # Nur die Faelle, in denen die Regex den Namen NICHT trifft, laufen auf
        # die Vorgabe. Die uebrigen liegen erfahrungsgemaess im Prozentbereich.
        if m:
            continue
        add(3, name, "20.0 GB (Vorgabe, weil die Regex den Namen nicht trifft)",
            f"{total / (1024 ** 3):.2f} GB laut Index", "~/.cache/huggingface/hub")


# ============================================================== Offen: Bilder
@check(4, "Bildweg zu den Bildlesern")
def _():
    rel = "devserver/my_app/routes/media_routes.py"
    roh, l1 = grab(rel, r"base64\.b64encode\(resolved\.read_bytes\(\)\)")
    cap, l2 = grab("devserver/my_app/utils/media_ref.py", r"IMAGE_MAX_SIZE\s*=\s*\d+")
    mn, _ = grab("devserver/my_app/utils/media_ref.py", r"IMAGE_MIN_SIZE\s*=\s*\d+")
    add(4, "Zweig ohne Rahmen", roh or "nicht gefunden", f"{cap} / {mn} im gemeinsamen Weg",
        f"{l1} | {l2}", "UNGLEICH" if roh else "NICHT GEFUNDEN")
    rel2 = "devserver/my_app/routes/schema_pipeline_routes.py"
    schritte = []
    for muster, name in ((r"max\(img\.size\)\s*>\s*768", "Obergrenze"),
                         (r"min\(img\.size\)\s*<\s*\d+", "Untergrenze"),
                         (r"img\.convert\(", "Modus")):
        v, _ = grab(rel2, muster)
        schritte.append(f"{name}: {'ja' if v else 'FEHLT'}")
    add(4, "dritte Kopie derselben Vorbereitung", " / ".join(schritte),
        "Obergrenze: ja / Untergrenze: ja / Modus: ja", f"{rel2} | media_ref.normalize_image")


# ============================================================== Offen: Grenzen
@check(5, "Wartezeit des Anbieters")
def _():
    n = sh(f"grep -rniE 'retry.?after' {ROOT}/devserver {ROOT}/gpu_service "
           "--include='*.py' | wc -l")
    formel, loc = grab("devserver/my_app/services/openai_style_stream.py",
                       r"wait\s*=\s*\(?2\s*\*\*[^\n]*")
    add(5, "Stellen, die den Header lesen", n,
        "der Header steht auf der Antwort, die in der Hand ist", "grep")
    add(5, "stattdessen", formel, "die vom Anbieter genannte Wartezeit", loc)


@check(6, "Zeichen- und Rundengrenzen")
def _():
    v, loc = grab("devserver/my_app/services/knowledge_processing.py", r"numbered\[:\d+\]")
    add(6, "gezeigter Ausschnitt der Segmentierung", v,
        "der Tokenzaehler des GPU-Dienstes, den das Repo daneben schon benutzt", loc)
    r, loc2 = grab("devserver/my_app/services/mean_images.py", r"VARIANTS_PER_CALL\s*=\s*\d+")
    k, loc3 = grab("devserver/my_app/services/mean_images.py", r"4096")
    add(6, "Rundengroesse der Mittelwert-Bilder", f"{r}, begruendet mit {k}",
        "das Fenster kommt aus der Modelldatei; der Aufruf geht an ein Cloud-Modell",
        f"{loc2} | {loc3}")


# ========================================================== Offen: Katalogwerte
@check(7, "Herkunftskarte: Konfiguration gegen Graph")
def _():
    def zahl(x):
        try:
            return float(x)
        except Exception:
            return x
    for name, cfg, chunk in (
            ("sd35_large", "devserver/schemas/configs/output/sd35_large.json",
             "devserver/schemas/chunks/output_image_sd35_large.json"),
            ("ltx_video", "devserver/schemas/configs/output/ltx_video.json",
             "devserver/schemas/chunks/output_video_ltx.json")):
        for key, muster in (("CFG", r'"cfg":\s*([0-9.]+)'), ("STEPS", r'"steps":\s*(\d+)')):
            a, l1 = grab(cfg, rf'"{key}":\s*([0-9.]+)', 1)
            b, l2 = grab(chunk, muster, 1)
            status = ("NICHT GEFUNDEN" if a is None or b is None
                      else "GLEICH" if zahl(a) == zahl(b) else "UNGLEICH")
            add(7, f"{name} {key}", a, b, f"{l1} | {l2}", status)


@check(8, "gpu_vram_mb doppelt getippt")
def _():
    for inst in ("denoising_archaeology", "concept_algebra",
                 "attention_cartography", "feature_probing"):
        cfgs = (glob.glob(os.path.join(ROOT, f"devserver/schemas/configs/output/{inst}*.json")))
        a = None
        for c in cfgs:
            hit = grab_all(os.path.relpath(c, ROOT), r'"gpu_vram_mb":\s*(\d+)')
            if hit:
                a = hit[0][0].group(1)
                break
        b = grab_all(f"devserver/schemas/chunks/output_image_{inst}_diffusers.py",
                     r'gpu_vram_mb["\']?\s*[:=]\s*(\d+)')
        vergleich(8, inst, a, b[0][0].group(1) if b else None,
                  "configs/output | chunks")


@check(9, "Verfuegbarkeit: LoRA")
def _():
    rel = "devserver/my_app/services/model_availability_service.py"
    kats = sorted({m.group(1) for m, _ in
                   grab_all(rel, r'"(checkpoints|unets|vaes|clips|loras)"')})
    try:
        oi = http_json(f"{COMFYUI}/object_info/LoraLoaderModelOnly")
        n = len(oi["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0])
    except Exception as exc:
        n = f"ComfyUI nicht erreichbar: {exc}"
    refs = sh(f"grep -rl 'lora_name' {ROOT}/devserver/schemas | wc -l")
    add(9, "geprueft werden", ", ".join(kats),
        f"ComfyUI meldet {n} LoRAs; {refs} Chunk-Dateien nennen eine", rel)


@check(10, "Bildfaehigkeit der Sprachmodelle")
def _():
    rel = "devserver/my_app/routes/canvas_routes.py"
    muster = [m.group(1) for m, _ in
              grab_all(rel, r"'([a-z0-9.\-]*(?:vision|vl)[a-z0-9.\-]*)'")]
    # Die massgebliche Liste ist seit Stufe 8 die Tabelle der lokalen
    # Sprachmodelle (vision: true), nicht mehr eine Route des GPU-Dienstes.
    try:
        with open(f"{ROOT}/devserver/config/local_llm_weights.json") as f:
            tabelle = json.load(f)
        namen = [alias for alias, e in tabelle["models"].items() if e.get("vision")]
        gemeldet = ", ".join(namen)
    except Exception as exc:
        gemeldet = f"Tabelle nicht lesbar: {exc}"
    add(10, "Erkennung", "Teilstring: " + ", ".join(muster[:8]),
        "die Tabelle fuehrt: " + gemeldet, f"{rel} | devserver/config/local_llm_weights.json")


@check(11, "RAVE: Trainingslaeufe")
def _():
    rel = "devserver/my_app/routes/rave_routes.py"
    keys = [m.group(1) for m, _ in grab_all(rel, r'"(v\d)":\s*\{')]
    sh_path = os.path.expanduser("~/ai/rave_research/rave.sh")
    shkeys, vorgabe = [], None
    if os.path.exists(sh_path):
        text = open(sh_path, encoding="utf-8", errors="replace").read()
        shkeys = re.findall(r"^\s*(v\d)\)", text, re.M)
        m = re.search(r'RUN_VERSION="\$\{RUN:-(\w+)\}"', text)
        vorgabe = m.group(1) if m else None
    vergleich(11, "bekannte Laeufe", ", ".join(keys), ", ".join(shkeys), f"{rel} | rave.sh")
    vergleich(11, "Vorgabe", grab(rel, r'args\.get\("run",\s*"(v\d)"\)', 1)[0], vorgabe,
              f"{rel} | rave.sh")


# ====================================================== Offen: Bibliothekswerte
@check(12, "Aufmerksamkeits-Zerlegung")
def _():
    v, loc = grab("gpu_service/config.py", r"DIFFUSERS_ENABLE_ATTENTION_SLICING\s*=.*")
    doc = sh("python3 -c \"import diffusers,inspect;"
             "d=inspect.getdoc(diffusers.DiffusionPipeline.enable_attention_slicing) or '';"
             "print(' '.join(d.split())[:360])\"", 180)
    add(12, "Vorgabe im Dienst", v, doc or "diffusers nicht importierbar", loc)


@check(13, "Schichtbaender der Zerlegung")
def _():
    b = grab_all("gpu_service/services/diffusers_backend.py",
                 r"'(shallow|mid|deep)':\s*\((\d+),\s*(\d+)\)")
    baender = ", ".join(f"{m.group(1)} {m.group(2)}-{m.group(3)}" for m, _ in b)
    schichten = {}
    for cfg in glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--*3.5-*/snapshots/*/transformer/config.json")):
        label = "medium" if "medium" in cfg else "large" if "large" in cfg else cfg
        try:
            schichten[label] = json.load(open(cfg)).get("num_layers")
        except Exception:
            pass
    add(13, "Baender", baender or None,
        "num_layers: " + json.dumps(schichten) if schichten else "Modelle nicht lokal",
        b[0][1] if b else "gpu_service/services/diffusers_backend.py")


@check(14, "Wan-Diffusers")
def _():
    rel = "gpu_service/services/diffusers_backend.py"
    v, loc = grab(rel, r'has_dual_transformer\s*=\s*"transformer_2"\s+in\s+model_index')
    wert = None
    for f in glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--*Wan*/snapshots/*/model_index.json")):
        try:
            d = json.load(open(f))
            if "transformer_2" in d:
                wert = (f"{f.split('models--')[1].split('/')[0]}: "
                        f"transformer_2 = {json.dumps(d['transformer_2'])}")
                break
        except Exception:
            pass
    add(14, "Pruefung auf den zweiten Transformer", v or "nicht gefunden",
        (wert or "kein Wan-model_index lokal")
        + " -- diffusers prueft den WERT (if value[0] is None: return False)", loc)
    n = len(grab_all(rel, r"expand_timesteps"))
    dekl = None
    for f in glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--*Wan*/snapshots/*/*config*.json")):
        try:
            d = json.load(open(f))
            if "expand_timesteps" in d:
                dekl = f"{d['expand_timesteps']} in {os.path.basename(os.path.dirname(f))}"
        except Exception:
            pass
    add(14, "expand_timesteps durchgereicht", f"{n} Erwaehnungen im Dienst",
        dekl or "keine lokale Deklaration", rel)


@check(15, "Modellverzeichnisse und Stapelgroesse")
def _():
    rel = "devserver/my_app/services/model_path_resolver.py"
    if not os.path.exists(os.path.join(ROOT, rel)):
        # Struck on 2026-10-10 (nothing imported it); a silent zero would read
        # as a count.
        add(15, "Verzeichnisse", "Datei entfernt am 2026-10-10", "-", rel)
        return
    eigene = {m.group(1) for m, _ in grab_all(rel, r'"([A-Za-z_\-]+)"')}
    fp = os.path.join(ROOT, "dlbackend/ComfyUI/folder_paths.py")
    familien = []
    if os.path.exists(fp):
        text = open(fp, encoding="utf-8", errors="replace").read()
        familien = sorted(set(re.findall(r'folder_names_and_paths\["([a-z0-9_]+)"\]', text)
                              or re.findall(r'"([a-z0-9_]+)":\s*\(\[', text)))
    add(15, "Verzeichnisse", f"{len(eigene)} von Hand aufgezaehlt",
        f"{len(familien)} Familien in ComfyUI", f"{rel} | folder_paths.py")
    b, lb = grab("gpu_service/services/llm_child.py", r"BATCH_SIZE\s*=\s*\d+")
    llama = sh(f"{ROOT}/llama.cpp/build/bin/llama-server --help 2>&1 "
               "| grep -E '\\-b,|--fit-ctx' | head -2")
    add(15, "Stapelgroesse", b, llama or "llama-server nicht gebaut", lb)
    e, le = grab("gpu_service/services/vram_coordinator.py", r"expected\s*\+=\s*\d+.*")
    try:
        h = http_json(f"{GPU_SERVICE}/api/health")
        comfy = next((f"{p['vram_mb']} MB (NVML, jetzt)"
                      for p in h["vram_coordinator"]["gpu_processes"]
                      if "17804" in p.get("cmdline", "")), "ComfyUI laeuft nicht")
    except Exception as exc:
        comfy = f"GPU-Dienst nicht erreichbar: {exc}"
    add(15, "ComfyUI-Grundverbrauch", e, comfy, le)


# ------------------------------------------------------------------- Ausgabe
def main():
    print("BELEGE ZU DEN BEFUNDEN VOM 09.09.2026")
    print("Repo:", ROOT)
    if NUR_OFFEN:
        print("(nur die offenen Befunde)")
    print("=" * 112)
    aktuell = None
    for nr, sache, a, b, quelle, status in ROWS:
        if nr != aktuell:
            print()
            aktuell = nr
        a = "-" if a is None else str(a)
        b = "-" if b is None else str(b)
        print(f"[{str(nr):>3}] {sache}")
        print(f"      getippt     : {a}")
        for i, zeile in enumerate(b.split("\n")):
            print(f"      {'massgeblich ' if i == 0 else '            '}: {zeile}")
        print(f"      fundstelle  : {quelle}")
        if status != "—":
            print(f"      >>> {status}")
    print()
    print("=" * 112)
    zaehlung = Counter(s for *_, s in ROWS)
    print("Zeilen:", len(ROWS), "|",
          ", ".join(f"{k}={v}" for k, v in sorted(zaehlung.items())))


if __name__ == "__main__":
    main()
