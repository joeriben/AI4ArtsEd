# ARCHITECTURE PART 36 — Marking AI-Generated Content

**Status:** implemented (image + video + audio metadata layer; image invisible layer; optional visible layer)
**Module:** `devserver/my_app/services/watermark_service.py`
**Framing:** pedagogical ethics; the wording of the norm in section 8

---

## 1. Why we mark — pedagogical rationale

The platform marks the AI-generated outputs it hands out, in the file itself, at the metadata layer — what and where in section 2, the cases where it does not in section 7. The wording of Article 50 of Regulation (EU) 2024/1689 stands in section 8. These are the principles the marking was built on:

1. **Transparency about AI authorship is itself a pedagogical value.** A platform that teaches media literacy must model the practice it teaches. If we ask learners to recognize AI-generated content, our own outputs should be recognizable.

2. **Learners retain authorship of their artifacts.** A marked output lets a participant later say "I made this in workshop X with these tools," even after the file has been emailed, screenshotted, re-encoded. The marking serves the learner's self-determination, not external authorities.

3. **Modality equality.** The principle that AI-generated content should be markable does not care whether the file is an image, an audio file, or a video. We mark all three at the metadata layer. The invisible layer is currently only available for images; extending it to audio and video is on the roadmap, gated only by technical feasibility.

4. **Honesty toward non-consenting third parties.** When a workshop output leaves the workshop — and we know it sometimes does, often by pedagogical design — it may be seen by people (parents, peers, online audiences) who did not consent to interact with AI-generated material. The mark gives them a chance to recognize what they are looking at.

5. **No surveillance infrastructure.** Marking serves the learner and the workshop community. It does not serve a central authority, a verification market, or an external compliance regime. We do not run a public verifier service, we do not sign markings with certificate chains routed through a Trust Authority, and we do not maintain a central database of who generated what.

---

## 2. What we mark, and how

| Modality | Metadata layer | Invisible layer | Visible layer (optional) |
|---|---|---|---|
| **Image (PNG)** | XMP iTXt + tEXt chunks | DWT-DCT (imwatermark) | Pillow text overlay with outline |
| **Image (JPEG)** | EXIF + XMP spliced in as APP1 segments — no re-encode | DWT-DCT (imwatermark) | Pillow text overlay with outline |
| **Image (WebP, single frame)** | XMP | — | Pillow text overlay |
| **Image (animated GIF/WebP/APNG)** | none — see below | — | — |
| **Video (MP4/WebM/MKV)** | ffmpeg container atoms (`-c copy`, lossless; mp4 needs `-movflags use_metadata_tags`) | not yet — roadmap | ffmpeg `drawtext` filter |
| **Audio (MP3/FLAC/M4A)** | ffmpeg container metadata (`-c copy`, lossless) | not yet — roadmap | not implemented |
| **Audio (WAV)** | XMP packet in a RIFF `_PMX` chunk, appended after ffmpeg | not yet — roadmap | not implemented |
| **3D (GLB)** | glTF `asset.extras`, JSON chunk rebuilt, BIN chunk untouched | — | — |
| **Vector (SVG)** | XMP packet in the SVG's own `<metadata>` element | — | — |
| **Sketch code (p5.js, Tone.js, Sonic Pi)** | comment header at the head of the file | — | the header IS visible |

All marking is **fail-open**: if any layer fails, the original bytes are written and a warning is logged. The platform never blocks output generation because of a marking issue.

**Why WAV is its own row.** RIFF INFO knows a fixed set of four-character fields;
the muxer silently drops `DigitalSourceType`, so a WAV came out carrying only the
plain description while every picture carried the controlled vocabulary. The XMP
specification names the carrier for RIFF: a top-level chunk with the ID `_PMX`
holding the UTF-8 packet (the letters are reversed — that is in the specification,
from a byte-order bug in the first implementation). The same trap sits in the mp4
muxer, where `-movflags use_metadata_tags` is what keeps a non-standard key alive.

**A JPEG is not re-encoded to be marked.** Pillow's `save()` always re-encodes,
and a JPEG loses a little every time. That matters more here than elsewhere: the
denoising instrument hands back full-resolution JPEG steps and exists so that
people can study exactly that material. So the two APP1 segments are spliced
into the marker stream after SOI and the entropy-coded data is never read —
pixel-identical, measured. Only when a visible or invisible layer has to be
DRAWN does the picture go through an encoder at all.

**An animated picture is left alone.** Pillow writes frame one and drops the
rest, so marking an 8-frame GIF returned a still. A format with no metadata slot
is now handed back untouched rather than re-saved: unmarked is a smaller loss
than flattened. This costs GIF and animated WebP their marking, and that is the
trade named openly here rather than discovered later in a file.

**Two values, not one.** `trainedAlgorithmicMedia` says the medium came out of a
model trained on sampled content. IPTC keeps a second value, `algorithmicMedia`,
for media a pure algorithm produced with no training data at all — and eSpeak NG
is exactly that: formant synthesis out of rules, nothing trained, nobody
recorded. A caller that knows better passes `digital_source_type` in the entity
metadata; everything else gets the trained value, which is the safer claim to
over-state. Where a later, better-informed caller wants to correct an earlier
mark, it can: the "already marked" short-circuit compares against the value
about to be written, not against "any known value", so the speech route can fix
what the executor stamped before it knew which system had spoken.

**Routed by content, not by name.** The dispatcher sniffs the magic bytes and
only falls back to the entity's name when they say nothing. The names on disk
have been demonstrably wrong: 57 files called `output_image` are mp3, one is an
mp4, ten called `output_video` are PNG, and `output_image_composite` — the
composed comparison sheets — appeared in no name list at all. Every one of those
went through the wrong branch, or through none, for as long as the dispatcher
trusted names.

**What is never marked.** `watermark_media_bytes` refuses entity names that
denote material a PERSON brought in (`input*`, `upload*`, `source_*`,
`recording*`, `user_*`). Here the name is the only evidence there is — the bytes
of an uploaded photograph look exactly like the bytes of a generated one — and
marking a person's own photograph as AI-generated would be the false statement
this service exists to prevent. The upload path therefore only ever *carries
over* a marking that was already in the file (`carry_disclosure_pnginfo`); it
never creates one.

The metadata layer in all modalities encodes the IPTC controlled-vocabulary marker `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia` (the same identifier ISO 22144 specifies for AI-generated media), plus a human-readable description string that includes model, date, and — only when the operator opts in — seed and prompt.

---

## 3. Disclosure of the invisible layer

The invisible image watermark is steganography. It modifies pixel values in the wavelet/DCT domain in a way that the eye does not perceive, but a corresponding decoder can recover. This raises an honest ethical question: are we hiding something from learners?

Our position:

- The invisible layer exists for one specific purpose: **forensic recovery for the learner's benefit**. If a workshop output circulates after metadata has been stripped (screenshot, re-upload to social media, re-encoding through a chat app), the invisible mark survives. This lets a learner later prove "yes, this came from my workshop session."
- We do **not** hide its existence. Workshop materials should mention the marking, and the architecture is documented here so that anyone — operator, participant, third-party auditor — can inspect what we do.
- The invisible payload is intentionally minimal: a short marker string, currently a generic `"AI-generated"` text, operator-configurable. It is **not** a unique per-output identifier that could be used to track a participant across sessions.
- Workshop leaders are encouraged to make the marking itself a teaching object. Why do we mark? What is steganography? Who benefits from the choice to mark visibly versus invisibly versus not at all? These are the media-literacy questions the platform is designed to support.

---

## 4. Integration points

**This was a single chokepoint until 2026-08-15 and is no longer one.** The
premise below — "every generation backend flows through `save_entity()`" — was
true of the schema pipeline and false of everything else, and the pages that do
not go through it are exactly the ones a workshop uses most.

There are now four places, and each is there for a reason the others cannot
cover:

| Place | Covers | Why it cannot be done elsewhere |
|---|---|---|
| `LivePipelineRecorder.save_entity()` | everything the schema pipeline writes to disk | the original chokepoint |
| `CanvasRecorder.save_entity()` | the canvas, a second complete production path | writes its own files, never touches the recorder above |
| `LatentLabRecorder` (both write sites) | latent-lab outputs AND intermediate steps | same — it writes past `save_entity` |
| `PipelineExecutor` result metadata | the base64 a run hands BACK to the page | the lab displays and downloads what it was handed, never the file on disk |

Plus the paths that persist nothing, or persist past every recorder, and must
therefore be marked where they are:

| Place | Covers |
|---|---|
| `/api/speech` | the platform's voice — stored nowhere, so marked on the way out |
| `parrot_service` | the sung answer, written straight into the recording folder |
| `mosaic_routes`, `cross_aesthetic_routes`, `fusion_workbench_routes` | three proxied workshops whose result never passes the executor |
| `rave_routes` | the model's own reconstructions, marked on the way out (the originals next door are a person playing and stay untouched) |
| `POST /api/media/mark` | files the BROWSER assembled — see below |

**What the browser assembles.** A few media never exist on this server at all.
The cross-modal bench decodes a generated sound into an `AudioBuffer`, lets
someone loop and shape it, and writes a completely new WAV out of the samples:
44 fresh header bytes, and nothing of what the platform had written into the
sound. Such a file can only be marked where the writers live, so the page hands
the finished bytes to `/api/media/mark` on the way to whoever is saving them.
Nothing is stored there; the bytes are marked and handed straight back, and a
failure returns them unchanged — a download that does not happen is worse than
one that carries nothing. `src/composables/useMediaMarking.ts` is the client
side of it.

The hook itself is the same everywhere:

```python
if isinstance(content, bytes):
    try:
        from my_app.services.watermark_service import watermark_media_bytes
        content = watermark_media_bytes(content, entity_type, metadata or {})
    except Exception as e:
        logger.warning(f"[RECORDER] watermark service unavailable ({e})")
self._write_file(filepath, content)
```

No chunk needed modification: the marking sits between the chunks and the
disk, and between the run and the page. Where the frontend fetches media via
`/api/media/{type}/{run_id}/{index}` it streams from disk and the disk state is
authoritative. Where the frontend was handed base64 in the response — every
latent-lab download button — the payload is now marked before it leaves the
executor, so the two copies say the same thing.

Marking is **idempotent**: a picture that already carries the disclosure comes
straight back out of `watermark_image_bytes` (unless a visible or invisible
layer is switched on, which has to be drawn either way). Without that, a picture
that passes two of the four points would be decoded and re-encoded twice — and on
a JPEG, that costs a little of the picture each time.

---

## 5. Public API

```python
watermark_media_bytes(content: bytes, entity_type: str, entity_metadata: dict | None = None) -> bytes
watermark_image_bytes(content: bytes, entity_metadata: dict | None = None) -> bytes
watermark_video_bytes(content: bytes, entity_metadata: dict | None = None) -> bytes
watermark_audio_bytes(content: bytes, entity_metadata: dict | None = None) -> bytes

watermark_glb_bytes(content: bytes, entity_metadata: dict | None = None) -> bytes
watermark_svg_bytes(content: bytes, entity_metadata: dict | None = None) -> bytes
watermark_code_bytes(content: bytes, entity_type: str, entity_metadata: dict | None = None) -> bytes

read_media_disclosure(path) -> dict            # was steht wirklich in der Datei
carry_disclosure_pnginfo(source_info) -> PngInfo | None   # beim Umkodieren mitnehmen
watermark_result_metadata(metadata: dict, entity_metadata: dict | None = None) -> None
                                               # markiert base64-Medien IN PLACE
```

Dispatch goes by the magic bytes: image / video / audio / glb / svg / text. Text
is marked only when the entity IS a sketch the run hands back as its medium
(`p5`, `tonejs`, `sonicpi`, `output_code`); prompts, readings and workflows pass
through untouched. Material a person brought in is never marked (see §2). When
the bytes say nothing, the entity name decides as a fallback.

`watermark_result_metadata` walks the base64 media a finished run carries back
to the page — `image_data`, `audio_data`, `video_data`, `mesh_data`,
`reference_image`, `result_image`, `mosaic_base64`, `audio_base64`, and each
entry in `archaeology_data.step_images` — and marks them in place. Not
`image_base64`: that name also carries the picture a user brought IN.

### Zurücklesen (seit 2026-08-15)

`read_media_disclosure(path)` ist die Umkehrung von `watermark_media_bytes`: Es
**öffnet die Datei**, statt zu berichten, was wir zu schreiben glauben — Art. 50
verlangt, dass die Kennzeichnung MIT dem Medium reist, also ist die Datei die
einzige ehrliche Auskunft. Bilder über Pillow (PNG-Text-Chunks, XMP, EXIF),
Container über `ffprobe`. Wirft nie; jeder Fehlschlag heißt `marked: False`.

Vier Felder tragen die Antwort:

| Feld | Bedeutung |
| --- | --- |
| `present` | War die Datei überhaupt da? Eine fehlende Datei ist KEINE unmarkierte — die Oberfläche lässt die Zeile dann weg, statt etwas über Ungelesenes zu behaupten. |
| `marked` | Kennzeichnung gefunden. |
| `standard` | `iptc-digitalsourcetype` = das kontrollierte Vokabular steht in der Datei; `text` = nur die Klartextzeile hat überlebt (der mp4-Muxer wirft unbekannte Schlüssel weg). |
| `carrier` | Wo sie gefunden wurde: `png-text`, `xmp`, `exif`, `container`. |

Route: `GET /api/media/disclosure/<run_id>[/<index>]?type=<medium>`; ohne
Treffer für `type` fällt sie auf die letzte Ausgabe des Laufs zurück, und die
Antwort nennt, was tatsächlich gelesen wurde. Eine unmarkierte Datei ist 200 mit
`marked: false`, kein Fehler — auf einer Karte ist das die interessantere
Auskunft.

**Zwei Lücken, die das Zurücklesen selbst gefunden hat** (2026-08-15):

1. **JPEG ging ungekennzeichnet aus dem Haus.** Der JPEG-Zweig hing an `piexif`,
   das in keiner requirements-Datei steht und nicht installiert ist; die
   `except ImportError` war damit der Normalfall, nicht die Ausnahme. Gemini gibt
   JPEG-Bytes zurück (die Plattform legt sie unter `.png` ab). Behoben ohne neue
   Abhängigkeit: Pillow 11 schreibt dieselben zwei EXIF-Felder und das
   XMP-Paket selbst; `piexif` bleibt der bevorzugte Weg, wo es installiert ist.
2. **Jede Umkodierung tilgte die Kennzeichnung.** `/api/media/upload/image`
   speichert neu (`Image.save`), und Pillow schreibt ohne `pnginfo=` keine
   Text-Chunks. Die Fläche lädt jedes gefallene Bild dorthin zurück — die Kopie,
   die auf dem Tisch liegt und heruntergeladen wird, trug also nichts, während
   die Karte „gekennzeichnet" sagte. `carry_disclosure_pnginfo` nimmt XMP und
   Text-Chunks des Originals mit; das gilt auch für ein gekennzeichnetes Bild,
   das jemand von außen mitbringt.

---

## 6. Configuration

Defaults live in `config._SETTINGS_DEFAULTS['WATERMARK']` and can be overridden via `user_settings.json`:

```json
{
  "metadata_image": true,
  "metadata_video": true,
  "metadata_audio": true,
  "metadata_3d": true,
  "metadata_svg": true,
  "metadata_code": true,
  "metadata_include_model": true,
  "metadata_include_date": true,
  "metadata_include_prompt": false,
  "metadata_include_seed": false,
  "software_name": "",
  "visible_image": false,
  "visible_video": false,
  "visible_text": "AI-generated",
  "visible_position": "bottom-right",
  "visible_opacity": 0.3,
  "invisible_image": false,
  "invisible_payload": "AI-generated"
}
```

**Notes for workshop operators:**
- `software_name` is intentionally empty by default. The platform is deployment-neutral. If your institution wants its name embedded in the metadata (e.g. `"UCDCAE Workshop 2026 Berlin"`), set it here. This is useful for later attribution if outputs circulate; it is not required.
- `metadata_include_prompt` defaults to `false` because workshop prompts can contain participant-supplied personal data. Turn this on only with full awareness of what gets written into every generated file's metadata.
- `visible_image` / `visible_video` are operator-configurable. Some workshops will want them on as a constant visual reminder; others (e.g. fine-art contexts) will prefer the unmodified output. The choice belongs to the workshop leader.
- `invisible_image` is opt-in. Workshops that emphasize provenance/forensics may turn it on; workshops that are uncomfortable with steganography in participant work may leave it off.

---

## 7. Failure modes (fail-open)

| Failure | Behavior |
|---|---|
| `config.WATERMARK` missing | Returns original bytes, warning logged |
| Pillow / piexif / imwatermark not importable | Skips that layer, warning logged |
| `ffmpeg` not in `PATH` | Skips video/audio watermark, warning logged |
| ffmpeg return code non-zero | Returns original bytes, warning with stderr excerpt |
| ffmpeg timeout (60–120 s) | Returns original bytes, warning logged |
| Image decode fails | Returns original bytes, warning logged |
| Visible draw raises | Image saved without overlay, warning logged |
| Invisible encode raises | Image saved without invisible layer, warning logged |
| `entity_type` unknown | Pass-through, no log |
| Audio format undetectable | Skips audio watermark, warning logged |

Pedagogical reasoning: a transient marking issue must not stop a workshop. A missing AI-origin tag on a single artifact is recoverable through workshop context. A failed generation that blocks a participant from continuing is not.

---

## 8. The wording this concerns

Regulation (EU) 2024/1689 (AI Act), quoted from EUR-Lex, English and German
text, retrieved 2026-09-22:
<https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R1689>

Article 50 stands in Chapter IV, "TRANSPARENCY OBLIGATIONS FOR PROVIDERS AND
DEPLOYERS OF CERTAIN AI SYSTEMS", and is headed "Transparency obligations for
providers and deployers of certain AI systems".

**Article 50(2)**

> Providers of AI systems, including general-purpose AI systems, generating
> synthetic audio, image, video or text content, shall ensure that the outputs
> of the AI system are marked in a machine-readable format and detectable as
> artificially generated or manipulated. Providers shall ensure their technical
> solutions are effective, interoperable, robust and reliable as far as this is
> technically feasible, taking into account the specificities and limitations of
> various types of content, the costs of implementation and the generally
> acknowledged state of the art, as may be reflected in relevant technical
> standards. This obligation shall not apply to the extent the AI systems
> perform an assistive function for standard editing or do not substantially
> alter the input data provided by the deployer or the semantics thereof, or
> where authorised by law to detect, prevent, investigate or prosecute criminal
> offences.

> (2)   Anbieter von KI-Systemen, einschließlich KI-Systemen mit allgemeinem
> Verwendungszweck, die synthetische Audio-, Bild-, Video- oder Textinhalte
> erzeugen, stellen sicher, dass die Ausgaben des KI-Systems in einem
> maschinenlesbaren Format gekennzeichnet und als künstlich erzeugt oder
> manipuliert erkennbar sind. Die Anbieter sorgen dafür, dass — soweit technisch
> möglich — ihre technischen Lösungen wirksam, interoperabel, belastbar und
> zuverlässig sind und berücksichtigen dabei die Besonderheiten und
> Beschränkungen der verschiedenen Arten von Inhalten, die Umsetzungskosten und
> den allgemein anerkannten Stand der Technik, wie er in den einschlägigen
> technischen Normen zum Ausdruck kommen kann. Diese Pflicht gilt nicht, soweit
> die KI-Systeme eine unterstützende Funktion für die Standardbearbeitung
> ausführen oder die vom Betreiber bereitgestellten Eingabedaten oder deren
> Semantik nicht wesentlich verändern oder wenn sie zur Aufdeckung, Verhütung,
> Ermittlung oder Verfolgung von Straftaten gesetzlich zugelassen sind.

**Article 50(4), first subparagraph**

> Deployers of an AI system that generates or manipulates image, audio or video
> content constituting a deep fake, shall disclose that the content has been
> artificially generated or manipulated. This obligation shall not apply where
> the use is authorised by law to detect, prevent, investigate or prosecute
> criminal offence. Where the content forms part of an evidently artistic,
> creative, satirical, fictional or analogous work or programme, the
> transparency obligations set out in this paragraph are limited to disclosure
> of the existence of such generated or manipulated content in an appropriate
> manner that does not hamper the display or enjoyment of the work.

> (4)   Betreiber eines KI-Systems, das Bild-, Ton- oder Videoinhalte erzeugt
> oder manipuliert, die ein Deepfake sind, müssen offenlegen, dass die Inhalte
> künstlich erzeugt oder manipuliert wurden. Diese Pflicht gilt nicht, wenn die
> Verwendung zur Aufdeckung, Verhütung, Ermittlung oder Verfolgung von Straftaten
> gesetzlich zugelassen ist. Ist der Inhalt Teil eines offensichtlich
> künstlerischen, kreativen, satirischen, fiktionalen oder analogen Werks oder
> Programms, so beschränken sich die in diesem Absatz festgelegten
> Transparenzpflichten darauf, das Vorhandensein solcher erzeugten oder
> manipulierten Inhalte in geeigneter Weise offenzulegen, die die Darstellung
> oder den Genuss des Werks nicht beeinträchtigt.

**Who the two words name — Article 3(3) and 3(4)**

> (3) ‘provider’ means a natural or legal person, public authority, agency or
> other body that develops an AI system or a general-purpose AI model or that has
> an AI system or a general-purpose AI model developed and places it on the
> market or puts the AI system into service under its own name or trademark,
> whether for payment or free of charge;

> (4) ‘deployer’ means a natural or legal person, public authority, agency or
> other body using an AI system under its authority except where the AI system is
> used in the course of a personal non-professional activity;

**From when — Article 113**

> It shall apply from 2 August 2026.
>
> However:
>
> (a) Chapters I and II shall apply from 2 February 2025;
>
> (b) Chapter III Section 4, Chapter V, Chapter VII and Chapter XII and Article
> 78 shall apply from 2 August 2025, with the exception of Article 101;
>
> (c) Article 6(1) and the corresponding obligations in this Regulation shall
> apply from 2 August 2027.

> Sie gilt ab dem 2. August 2026.

Chapter IV is not among the three exceptions.

No assessment of this platform's own role is written here. The section that
stood in this place until 2026-09-22 made one — not a provider under Article
50(2), not a deployer under Article 50(4), therefore "freiwillige
Übererfüllung" — without quoting a single line of the Regulation, and dated
from before the Article became applicable. It was deleted. What replaces it
is the wording; the assessment is not this document's to make.

## 9. Roadmap

These are open items, prioritized by pedagogical value rather than compliance pressure:

1. **Invisible watermark for audio and video.** Modality equality is one of our stated principles. Image is currently the only modality with an invisible layer. Audio watermarking requires a dedicated library (`audiowmark`, perceptual masking in the frequency domain); video watermarking requires frame-level processing. Both are technically possible; neither is trivial. Will be added when feasible.
2. **Workshop-facing materials documenting the marking.** A short, accessible explanation for workshop leaders and (age-appropriate) for participants: what we mark, why, how they can verify. This makes the invisible layer transparent and turns it into a teaching object.
3. **Provenance card export (separate feature).** A human-readable summary sheet (PDF or HTML) that workshop participants can take home alongside their output: generation date, model, prompt (when pedagogically appropriate), workshop name. Tracked separately from this document.

---

## 10. Critical files

| File | Role |
|---|---|
| `devserver/my_app/services/watermark_service.py` | service implementation, public API |
| `devserver/my_app/services/pipeline_recorder.py` | hook in `save_entity()` |
| `devserver/my_app/services/canvas_recorder.py` | hook in `save_entity()` |
| `devserver/my_app/services/latent_lab_recorder.py` | hook at both write sites (`_marked`) |
| `devserver/schemas/engine/pipeline_executor.py` | marks the base64 a run hands back |
| `devserver/my_app/routes/media_routes.py` | `/api/media/disclosure/<run_id>` reads it back |
| `devserver/config.py` | `_SETTINGS_DEFAULTS['WATERMARK']` |
| `user_settings.json` | live operator-controlled values |
| `devserver/testfiles/test_watermark_standalone.py` | standalone test (image, video, audio, dispatcher, invisible roundtrip) |

---

## 11. Known limitations

- The invisible image watermark payload is capped at 32 characters; images smaller than 256 px on the short edge are skipped (DWT decomposition needs minimum frame size).
- Container metadata is stripped when files are re-encoded through a tool that does not preserve metadata. The invisible image layer is the mitigation against this for images; audio and video do not yet have an equivalent fallback. Innerhalb der Plattform ist der eine bekannte Umkodier-Punkt (Bild-Upload) seit 2026-08-15 abgedeckt, s. o.
- **Ogg trägt nichts.** Der ffmpeg-Ogg-Muxer schreibt beim `-c copy` überhaupt
  keine Vorbis-Kommentare — die Ausgabe kommt tag-los heraus, geprüft am
  2026-08-15. Kein Ausgabe-Config der Plattform erzeugt derzeit Ogg (Ton fällt
  in wav und mp3), die Lücke ist also latent und nicht live; sie zu schließen
  hieße, das Kommentar-Paket selbst zu schreiben.
- **Animierte Bilder tragen nichts** (GIF, animiertes WebP, APNG) — bewusst, s. §2.
- **MIDI trägt nichts.** `/api/media/midi/<run_id>` liefert aus, es gibt aber
  keinen Schreiber dafür und `MThd` erkennt der Schnüffler nicht. Kein
  Ausgabe-Config erzeugt derzeit MIDI; die Karte sagt für eine solche Datei
  ehrlich „keine in der Datei".
- **Der PDF-Bericht trägt den Beleg nur am Dokument.** `SessionExportView`
  kodiert jedes Bild über eine Canvas neu, bevor es eingebettet wird, und das
  streift die Kennzeichnung ab. Das Dokument selbst sagt jetzt in seinen
  Eigenschaften, dass es erzeugte Medien enthält; die unangetasteten,
  markierten Originale liegen im ZIP-Export daneben. Ein aus dem PDF
  herausgelöstes Einzelbild trägt nichts.
- **Das Standbild einer Skizze auf der Fluss-Fläche trägt nichts.**
  `x2x_flow.vue` rendert eine aufgenommene p5-Zeichenfläche über
  `canvas.toDataURL` in ein JPEG für die Karte. Es gibt keinen
  Herunterladen-Knopf dafür, aber ein Bild lässt sich mit der rechten Maustaste
  sichern.
- **Das Code-Feld der JSON-Antwort trägt nichts.** Die Datei unter
  `/api/media/p5/<run_id>` ist markiert, das Feld `media_output['code']`
  daneben enthält die rohe Zeichenkette. Kein Herunterladen-Weg nimmt heute
  dieses Feld — der Sandkasten zeigt es in einem Textfeld. (Die Korrektur säße
  in `schema_pipeline_routes.py`; die Datei trägt gerade nicht-committete
  Änderungen einer parallelen Sitzung und wurde deshalb nicht angefasst.)
- For multimodal outputs (e.g. image-to-video chains), the marking is applied independently per artifact. We do not currently embed cross-references between artifacts of the same generation run; this is a possible future feature, not a current one.
