#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reruns the measurement the re-enactment routing rests on.

`resolve_singer` in `my_app/services/parrot_service.py` decides which of four
machines sings a recording back, from what the ranking station heard. The
docstring there names numbers; this is where they come from, so that nobody has
to take them on trust and so that the next person can see whether they still
hold after a model or vocabulary change.

    python3 devserver/testfiles/probe_parrot_routing.py [song.wav] [speech.wav]

Two of the four probes are made here, from nothing, so this runs on a fresh
install and so that no recording of anybody is used:

    noise        brown noise                  -> neither music nor speech
    instrumental synthesised chords + a kick   -> music without a voice

Two need a file, because neither a sung voice nor speech can be synthesised at
this end. The defaults are what the 2026-08-12 measurement used on the dev box:

    song    heartlib/assets/output.wav          (heartlib's own demo, sung)
    speech  ~/ai/tts_test/ref_de_piper.wav      (German speech, OUTSIDE the tree)

Give your own paths as arguments; any 10-240 s wav will do. Missing files are
skipped with a line saying so, not silently.

It prints, per probe: both rankings, what `_what_was_heard` made of them, and
which config `resolve_singer` chose. It runs the two rankers and the transcriber
through the GPU service — no generation, so it costs no song.
"""
import math
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
DEVSERVER = os.path.dirname(HERE)
sys.path.insert(0, DEVSERVER)
os.chdir(DEVSERVER)

SR = 44100
SECONDS = 12.0
OUT = "/tmp/ai4artsed_probe"


def _write(path, samples):
    peak = max(abs(x) for x in samples) or 1.0
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, x / peak * 0.9)) * 32000))
            for x in samples))
    return path


def make_noise(path):
    """Brown noise. Loud enough that the ranking station does not refuse it —
    it rejects digital silence outright, which is a different case."""
    import random
    rng = random.Random(20260812)
    n = int(SR * SECONDS)
    out, last = [0.0] * n, 0.0
    for i in range(n):
        last = max(-1.0, min(1.0, last + rng.uniform(-0.02, 0.02)))
        out[i] = last
    return _write(path, out)


def make_instrumental(path):
    """Music with nobody in it: ii-V-I-vi, plucked, over a soft kick."""
    n = int(SR * SECONDS)
    chords = [(293.66, 349.23, 440.00), (392.00, 493.88, 587.33),
              (261.63, 329.63, 392.00), (220.00, 261.63, 329.63)]
    buf = [0.0] * n
    bar_len = n // len(chords)
    for bar, chord in enumerate(chords):
        start = bar * bar_len
        for k, f in enumerate(chord):
            for rep in (0, 1):
                off = start + rep * bar_len // 2
                for i in range(bar_len // 2):
                    if off + i >= n:
                        break
                    t = i / SR
                    env = math.exp(-3.2 * t)
                    buf[off + i] += 0.18 * env * (
                        math.sin(2 * math.pi * f * t)
                        + 0.45 * math.sin(4 * math.pi * f * t)
                        + 0.22 * math.sin(6 * math.pi * f * t)) / (1 + 0.4 * k)
    for beat in range(0, n, bar_len // 2):
        for i in range(min(3000, n - beat)):
            t = i / SR
            buf[beat + i] += 0.35 * math.exp(-28 * t) * math.sin(
                2 * math.pi * (110 - 70 * min(t * 12, 1.0)) * t)
    return _write(path, buf)


def head(ranking, n=5):
    ordered = sorted(ranking or [], key=lambda e: -e["score"])[:n]
    return "  ".join(f"{e['label']} {e['score']:+.3f}" for e in ordered)


def main():
    os.makedirs(OUT, exist_ok=True)
    song = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(DEVSERVER), "heartlib", "assets", "output.wav")
    speech = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(
        "~/ai/tts_test/ref_de_piper.wav")

    probes = [
        ("noise", make_noise(os.path.join(OUT, "noise.wav")), "stableaudio_sfx"),
        ("song", song, "heartmula_standard"),
        ("speech", speech, "voxcpm_standard"),
        ("instrumental", make_instrumental(os.path.join(OUT, "instrumental.wav")),
         "stableaudio_music"),
    ]

    from my_app.services.media_analysis_client import get_media_analysis_client
    import my_app.services.parrot_service as ps

    analysis = get_media_analysis_client()
    rows = []
    for name, path, want in probes:
        if not os.path.exists(path):
            print(f"-- {name}: no file at {path}, skipped")
            continue
        clap = analysis.tag(path, model=ps.RANKER_PRIMARY[0])
        muq = analysis.tag(path, model=ps.RANKER_SECOND[0])
        heard = analysis.transcribe(path)
        text = (heard or {}).get("text", "")
        got = ps.resolve_singer(muq, text)
        rows.append((name, want, got, ps._what_was_heard(muq, text), text, clap, muq))

    print()
    print(f"{'probe':14} {'expected':20} {'chose':20} (music, text)  transcript")
    print("-" * 100)
    for name, want, got, heard, text, _, _ in rows:
        mark = "OK " if want == got else "XX "
        print(f"{mark}{name:11} {want:20} {got:20} {str(heard):14} "
              f"{(text or '').strip()[:36]!r}")

    print("\nrankings, top 5:")
    for name, _, _, _, _, clap, muq in rows:
        print(f"\n  {name}")
        print(f"    {ps.RANKER_PRIMARY[1]:16} {head(clap)}")
        print(f"    {ps.RANKER_SECOND[1]:16} {head(muq)}")

    print(f"\n{sum(1 for r in rows if r[1] == r[2])}/{len(rows)} as the table demands")
    return 0 if rows and all(r[1] == r[2] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
