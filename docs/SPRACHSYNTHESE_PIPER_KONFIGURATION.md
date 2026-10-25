# Sprachsynthese: Piper-Konfiguration und Feldstand

Stand 2026-08-08. Gemessen auf dem Dev-Server (Fedora, RTX PRO 6000); Piper und
Supertonic laufen auf der CPU.

Anlass: die in Betrieb befindliche Synthese (Qwen3-TTS) ist autoregressiv — sie
inferiert die Äußerung Wort für Wort und spricht weiter, wo nichts mehr steht.
Gemessen: ein bei Komma abgeschnittener Satzteil (57 Zeichen) kostete 16,3 s
Synthese für 15,0 s Ton, weil das Modell eine Fortsetzung erfand; derselbe Text
als ganzer Satz (83 Zeichen) kostete 4,7 s für 5,7 s Ton. Gesucht ist eine Stimme,
die genau den übergebenen Text spricht und nicht weiterredet.

## 1. Wie Piper konfiguriert wird

Paket `piper-tts` (Fork OHF-Voice/piper1-gpl, hier 1.6.0). Alle Angaben aus dem
installierten Quelltext, nicht aus Dokumentation.

### Parameter (`piper.SynthesisConfig`)

| Feld | Voreinstellung | Wirkung |
|---|---|---|
| `speaker_id` | `None` → `default_speaker_id` der Stimme (meist 0) | nur bei Mehrsprecher-Modellen |
| `length_scale` | aus der Stimm-JSON, sonst 1.0 | Tempo. Größer = langsamer |
| `noise_scale` | aus der Stimm-JSON, sonst 0.667 | Rauschen des Generators |
| `noise_w_scale` | aus der Stimm-JSON, sonst 0.8 | Schwankung der Lautdauern. Kleiner = gleichmäßiger |
| `normalize_audio` | **`True`** | siehe unten — in einer satzweisen Pipeline schädlich |
| `volume` | 1.0 | glatter Faktor auf die Samples |

`PiperVoice.load(..., use_cuda=True)` schaltet auf den CUDAExecutionProvider um
(braucht `onnxruntime-gpu`). Auf der CPU liegt Piper bei Faktor 0,01–0,08 der
Echtzeit; eine GPU ist dafür nicht nötig.

`voice.synthesize(text, syn_config)` liefert **einen Audio-Chunk pro Satz** —
die Satztrennung macht espeak-ng. Das ist der natürliche Streaming-Punkt.

### Die Falle: `normalize_audio`

`normalize_audio=True` teilt **jeden Satz einzeln** durch seinen eigenen Spitzenwert.
In einer satzweisen Pipeline — und genau so arbeitet die Plattform, damit die
ersten Wörter schnell kommen — springt damit die Lautstärke von Satz zu Satz.

Richtig ist: `normalize_audio=False`, und die Lautheit einmal über die ganze
Äußerung setzen (hier −18 LUFS nach EBU R128, `pyloudnorm`).

### Was die Einstellungen nicht können

Alle zehn deutschen Stimmen liefern denselben unangetasteten VITS-Standard aus
(`noise_scale 0.667`, `length_scale 1.0`, `noise_w 0.8`); einzige Ausnahme ist
`mls` mit 0.333 / 1.0 / 0.333. Niemand hat sie je eingestellt.

Ein Schwenk `length_scale ∈ {0.95, 1.05, 1.15}` × `noise_w ∈ {0.3, 0.55, 0.8}`
an `thorsten-high` und `pavoque-low` verschiebt Tempo (2,38 s bis 2,73 s bei
gleichem Satz) und Gleichmaß der Lautdauern. Die Stimme selbst verschiebt er nicht.

## 2. Der deutsche Piper-Katalog

Vollständig — mehr gibt es im offiziellen Repository nicht. Herkunft aus den
jeweiligen MODEL_CARD-Dateien.

| Stimme | Datensatz | Wer spricht | Rate | Lizenz | Training |
|---|---|---|---|---|---|
| thorsten low/medium/high | Thorsten-Voice | Thorsten Müller, privater Stimmspender, 23 h | 16 / 22 / 22 kHz | CC0 | aus engl. Ryan bzw. lessac nachtrainiert |
| thorsten_emotional | Thorsten-Voice | derselbe, 8 Emotionen | 22 kHz | CC0 | aus thorsten medium |
| pavoque | marytts/pavoque-data (DFKI) | Stefan Röttig, ausgebildeter Schauspieler und Opernbariton | 16 kHz | CC BY-NC-SA 4.0 | aus engl. Ryan nachtrainiert |
| kerstin | rhasspy/dataset-voice-kerstin | Spenderin | 16 kHz | CC0 | aus engl. Ryan nachtrainiert |
| karlsson, ramona, eva_k | M-AILABS | LibriVox-Vorleser:innen | 16 kHz | siehe Quelle | Ryan bzw. von Grund auf |
| mls | Multilingual LibriSpeech | **236** LibriVox-Freiwillige | 22 kHz | CC BY 4.0 | von Grund auf |

Zwei strukturelle Punkte:

1. Außer `thorsten` medium/high (und `mls`) ist **alles 16 kHz**.
2. Die meisten sind aus einer **englischen** Grundstimme nachtrainiert — englisches
   Prosodiemodell, deutsche Laute.

`mls` ist keine Stimme, sondern ein Forschungskorpus. Ohne `speaker_id` nimmt
Piper Sprecher 0 — eine beliebige der 236 Freiwilligen. Für ein Produkt
unbrauchbar, solange kein Sprecher ausgewählt und geprüft ist.

Gemeindestimmen außerhalb des Katalogs (`jarvis`, `miro`, `dii` bei ufozone /
OpenVoiceOS) sind entweder aus Thorsten-Voice nachtrainiert oder auf
**synthetischen** Daten trainiert, und in der ufozone-Fassung CC BY-NC-SA.

## 3. Sprachabdeckung der zehn Plattformsprachen

| | ar | bg | de | en | es | fr | he | ko | tr | uk | |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Piper | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 10 von 10 |
| Supertonic 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | 9 von 10 |
| Qwen3-TTS (in Betrieb) | — | — | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | — | 5 von 10 |

Piper bringt für Hebräisch einen eigenen Phonemisierer mit (Nakdimon-Vokalisierung
plus IPA-G2P), nicht nur espeak.

## 4. Feldstand 2025/26 — nicht-autoregressive Synthese

| Modell | Bauart | Deutsch | Größe | Lizenz | Eignung |
|---|---|---|---|---|---|
| Supertonic 3 (2026-04-29) | Flow Matching + Sprach-Autoencoder, ONNX | ja, 31 Sprachen | 99 M | OpenRAIL-M | Kandidat, gemessen |
| Piper | VITS mit Dauer-Prädiktor | ja, 10 Stimmen | keine Angabe der Hersteller | GPL-3.0-or-later (Code) | Kandidat, gemessen |
| Kokoro 82M | StyleTTS2 | offiziell nein; Gemeinde-Modell „Martin" | 82 M | Apache 2.0 | Kandidat, gemessen |
| Higgs Audio v2 | Llama-3.2-3B-Rückgrat + DualFFN | unklar | 3 B | — | autoregressiv |
| Sesame CSM | zwei autoregressive Llama-Transformer | unklar | 1 B | — | autoregressiv |
| dots.tts | kontinuierlich autoregressiv, Flow-Matching-Kopf | nicht genannt | 2 B | Apache 2.0 | autoregressiv |
| F5-TTS | DiT-Flow-Matching | Gemeinde-Modelle | 336 M | Gewichte CC-BY-NC | Lizenz |
| Chatterbox, XTTS v2 | autoregressiv | ja | 0,5–1 B | — | autoregressiv |

Supertonic 3: feste Preset-Stimmen (M1–M5, F1–F5), 44,1 kHz, `total_steps`
steuert die Flow-Schritte. Unter 4 Schritten wird es blechern; Voreinstellung 8.
Auf der CPU 1,4–5 s je Satz.

Kokoro auf Deutsch: eine einzige männliche Stimme („Martin", StyleTTS2-Stufe-2 auf
der Stimme von Martin Harbecke, aufgesetzt auf ein synthetisches
51-Sprecher-Grundmodell), 24 kHz, 0,28–0,36 s je Satz auf der CPU, ONNX,
Apache 2.0. Deutsche Textnormalisierung (Daten, Zahlen, Einheiten, Abkürzungen,
Euro-Beträge) liegt dem Modell bei.

Synthesezeit je Satz auf der CPU, dieselben drei Sätze: Piper 0,03–0,38 s ·
Kokoro 0,28–0,36 s · Supertonic 1,4–5,1 s. Qwen3-TTS auf der freien
RTX PRO 6000: 2,1–11,9 s.

## 5. Offen

- Die Stimmwahl selbst. Der Hörvergleich (alle Piper-Stimmen, alle
  Supertonic-Stimmen, Schrittzahl-Schwenk, Einstellungs-Schwenk) liegt vor;
  entschieden ist nichts.
- Supertonic auf der GPU (onnxruntime-gpu, CUDA 13) ist ungeprüft.
- Hebräisch: nur Piper hat es.
