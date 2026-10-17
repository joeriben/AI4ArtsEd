# Qualitätsstufen der Modelle

Die Karte neben einem Modell in der Modellwahl des Flow (an den Modell-Blasen unter einem Medium-Zeichen und am Modellnamen im Kasten „Vorbereitung“) zeigt den vollen Namen, Qualität und Tempo in je fünf Sternen und die geschätzte Dauer der Erzeugung. Dieselben vier Angaben zeigte die t2x-Seite (`text_transformation.vue`) an ihren Modell-Blasen, bis sie am 2026-08-12 entfernt wurde.

Die Qualitätsstufe steht als `quality_rating` in den Metadaten des Ausgabe-Chunks, den die Ausgabe-Config unter `OUTPUT_CHUNK` nennt: im Block `meta` eines JSON-Chunks, in `CHUNK_META` eines Python-Chunks. `GET /api/schema/output-cards` liest sie dort (`devserver/my_app/routes/schema_pipeline_routes.py`), `public/ai4artsed-frontend/src/composables/useOutputCards.ts` baut daraus die Karte.

Diese Datei hält fest, zwischen welchen Ankern die Stufe eingestuft wird, nach welchen Kriterien, und woher jede Stufe stammt. Sie ersetzt den Maßstab vom 2025-12-09, dessen Stufen von „Legacy/Deprecated“ bis „State-of-the-art“ reichten; er steht in einer Archivdatei außerhalb des Repositorys. Die Stufen, die vor diesem Maßstab gesetzt sind, stehen bis zu ihrer Prüfung weiter in den Chunks.

## Zweck

Die Sterne dienen der Orientierung bei der Modellwahl in der praktischen Nutzung.

## Maßstab

Die Stufe ist relativ zu zwei Ankern: dem technischen Optimum, das Amateuren am Markt zugänglich ist, und der niedrigsten Qualität generativer KI der Jahre 2021/22.

Daraus ergeben sich die Anker:

- **1 Stern:** die niedrigste Qualität generativer KI der Jahre 2021/22. Beispiele: bei Bildern VQGAN+CLIP (2021) und DALL·E mini (2021/22), bei Klang Riffusion (2022).
- **5 Sterne:** das technische Optimum, das Amateuren zum Zeitpunkt der Einstufung am Markt zugänglich ist. Zugänglich heißt hier: ohne eigene Rechenhardware und ohne professionelle Lizenz nutzbar, als Abo, App oder bezahlte Einzelnutzung. Ein offenes Modell, das nur auf eigener Hardware läuft, ist danach nicht der obere Anker.
- **2 bis 4 Sterne** liegen dazwischen.

Der obere Anker ist für kein Medium mit einem Produkt benannt (siehe „Offen“).

## Kriterien

Die Kriterien gelten vorläufig (siehe „Offen“).

1. **Je Medium.** Bild, Video, Klang und 3D, die Medien der Flow-Auswahl, werden jeweils zwischen ihren eigenen Ankern eingestuft; Musik zählt zu Klang. Drei Sterne bei einem Videomodell bedeuten eine andere Qualität als drei Sterne bei einem Bildmodell. Für Code ist offen, ob der Maßstab gilt.
2. **Die Einstellung der Plattform zählt.** Eingestuft wird, was ein Lauf auf dieser Plattform mit ihren Einstellungen liefert: Schrittzahl, Auflösung, Länge, destillierte oder beschleunigte Fassung. Die Bestleistung aus Paper, Modellkarte oder Release zählt dafür nicht.
3. **Ein typisches Ergebnis.** Eingestuft wird ein typisches Ergebnis zu einem typischen Workshop-Prompt, nach zwei Fragen: Wie genau folgt es dem Prompt? Wie sauber ist es gemacht? Die zweite Frage betrifft bei Bildern Anatomie, Artefakte und Schrift im Bild, bei Video dazu den Zusammenhang über die Zeit und die Bewegung, bei Klang die Tonqualität und bei Musik Aufbau und Gesang, bei 3D Geometrie und Textur.
4. **Ganze Sterne, kein Ersatzwert.** Wo keine Stufe gesetzt ist, zeigt die Karte keine Qualitätszeile. Die t2x-Seite zeigte in diesem Fall drei Sterne.
5. **Datiert.** Der obere Anker bewegt sich mit dem Markt. Eine Stufe wird neu geprüft, wenn ein neues Angebot den oberen Anker verschiebt oder die Plattform das Modell oder seine Einstellungen ändert.
6. **Jede Stufe hat eine Herkunft.** Die Tabelle unten nennt sie je Stufe: direkt gesetzt, aus einer Begründung übernommen oder vor diesem Maßstab gesetzt und nicht neu geprüft.

## Tempo und Dauer

Tempo und Dauer sind keine Einstufung. Beide folgen aus `estimated_duration_seconds` im Ausgabe-Chunk, gerechnet wie auf der t2x-Seite. Die Zahl schätzt nur den Schritt dieses Chunks, die Erzeugung; die Schritte davor (Übersetzung, Prüfung, Prompt Interception) sind darin nicht enthalten, und bei 3D ohne Bild auch nicht die Erzeugung des Bildes, die der Flow dem Modell vorschaltet. Mehrere Configs nennen eine andere Dauer als ihr Chunk (Stable Diffusion 3.5 Large: Config 20-60, Chunk 12; LTX Video: Config 5-15, Chunk 17-30); die Karte liest den Chunk. Die Dauer von Hunyuan3D-2 im Chunk (180-240) folgt der Messung aus Commit e6801077 (213 s bei 50 Schritten, Modell geladen), die zuvor nur in der Config stand. Das Tempo ist `floor((90 − s) / 18) + 1`, auf 1 bis 5 begrenzt, mit s als unterer Grenze eines Bereichs: 5 Sterne bis 18 s, 4 bis 36 s, 3 bis 54 s, 2 bis 72 s, 1 ab 73 s. HeartMuLa mit „30-240“ bekommt so 4 Sterne. Zu einer einzelnen Zahl kommt die Ladezeit der Gewichte hinzu, eine Sekunde je GB von `gpu_vram_mb`, gerundet, und die Dauer steht als Bereich da, wenn diese Ladezeit drei Sekunden oder mehr beträgt. Darunter, und wo der Chunk keinen VRAM-Wert nennt, steht die Zahl allein. Wo der Chunk keine Dauer nennt, 0 nennt (die zwei Code-Configs, deren Code ein Sprachmodell schreibt) oder eine, die sich nicht als Zahl lesen lässt, zeigt die Karte weder Tempo noch Dauer; die t2x-Seite zeigte dort drei oder fünf Sterne und „~1 sec“. Ob die geschätzten Dauern in den Chunks heutige Läufe treffen, ist nicht geprüft.

## Stand 2026-09-27

Die Karte zeigt den Namen aus dem Feld `name` der Config, die erste Spalte der Tabelle dagegen den Namen des Modells. Beide weichen voneinander ab, etwa „Image to 3D (Hunyuan3D-2)“ auf der Karte und „Hunyuan3D-2“ in der Tabelle. Aus dem Namen der Config `wan22_t2v_video_fast` ist der Zusatz „(ComfyUI)“ gestrichen; er nannte die Software, in der das Modell auf dem Server läuft. Die Karte liest den Chunk, den die Config unter `OUTPUT_CHUNK` nennt. Läuft Stable Audio 3 nicht, erzeugt der Flow mit dessen Ersatzweg Stable Audio Open 1.0, und die Karte zeigt weiter die Angaben von Stable Audio 3.

**Nachtrag 2026-10-01:** Stable Audio Open 1.0 ist von der Plattform entfernt und durch Stable Audio 3 ersetzt. Seither hat Stable Audio 3 keinen Ersatzweg; ein gescheiterter Lauf endet mit seinem eigenen Fehler. Die Zeile von Stable Audio Open 1.0 in der Tabelle bleibt als Beleg der Stufe 2, auf die sich die Begründung für Stable Audio 3 bezieht.

| Modell im Flow | Config | Chunk | Stufe | Herkunft |
|---|---|---|---|---|
| CommonCanvas XL C | `commoncanvas_xl_c` | `output_image_commoncanvas_xl_c` | 1 | gesetzt: höchstens 2, eine Stufe unter Stable Diffusion 3.5 Large Turbo |
| Stable Diffusion 3.5 Large Turbo | `sd35_large_turbo` | `output_image_sd35_turbo` | 2 | vor diesem Maßstab gesetzt, nach ihm geprüft und beibehalten |
| Stable Diffusion 3.5 Large | `sd35_large` | `output_image_sd35_large` | 3 | gesetzt |
| Flux 2 Dev | `flux2` | `output_image_flux2` | 4 | vor diesem Maßstab gesetzt, nicht neu geprüft |
| Gemini 3 Pro Image | `gemini_3_pro_image` | `output_image_gemini_3_pro` | 5 | vor diesem Maßstab gesetzt, nicht neu geprüft |
| Qwen Image Edit Lightning | `qwen_img2img` | `output_image_qwen_img2img` | 3 | aus der Begründung unten übernommen |
| Qwen 2511 Multi-Image Fusion | `qwen_2511_multi` | `output_image_qwen_2511_multi` | 4 | aus der Begründung unten übernommen |
| Wan 2.2 T2V 14B Fast | `wan22_t2v_video_fast` | `output_video_wan22_t2v_fast` | 4 | vor diesem Maßstab gesetzt, nicht neu geprüft |
| LTX Video | `ltx_video` | `output_video_ltx` | 2 | vor diesem Maßstab gesetzt, nicht neu geprüft |
| Wan 2.2 Image-to-Video (14B) | `wan22_i2v_video` | `output_video_wan22_i2v` | 4 | vor diesem Maßstab gesetzt, nicht neu geprüft |
| Stable Audio 3 | `stableaudio_open` | `output_audio_stableaudio_diffusers` | 3 | aus der Begründung unten übernommen |
| Stable Audio Open 1.0 (im Flow nur der Ersatzweg für Stable Audio 3, `fallback_chunk`) | – | `output_audio_stableaudio` | 2 | gesetzt |
| HeartMuLa | `heartmula_standard` | `output_music_heartmula` | 4 | gesetzt |
| Hunyuan3D-2 | `hunyuan3d_text_to_3d` | `output_3d_hunyuan3d` | 2 | gesetzt: höchstens 2; Begründung unten |
| p5.js | `p5js_code` | `output_code_p5js` | 1 | vor diesem Maßstab gesetzt, nicht neu geprüft |
| Tone.js | `tonejs_code` | `output_code_tonejs` | 1 | vor diesem Maßstab gesetzt, nicht neu geprüft |

## Begründung von vier Stufen

Jede Begründung stützt sich auf die Angaben des Herstellers, auf die Einstellungen, mit denen die Plattform das Modell laufen lässt, und auf die direkt gesetzten Stufen. Ergebnisse der Modelle auf dieser Plattform sind dafür nicht angesehen worden. Die vier Stufen stehen in den Chunks.

| Modell | Stufe | Begründung |
|---|---|---|
| Qwen Image Edit Lightning (`qwen_img2img`) | 3 | Das Grundmodell Qwen-Image-Edit erschien im August 2025 und hat rund 20 Mrd. Parameter; der Hersteller nennt beim Erscheinen „state-of-the-art (SOTA) performance in image editing tasks“ [1]. Die Plattform lässt es in FP8 mit der Lightning-LoRA in 4 Schritten laufen (CFG 1, 1,7 Megapixel); einen Qualitätsvergleich dieser Verkürzung mit dem vollen Lauf veröffentlicht der Hersteller der LoRA nicht [2]. Mit den Nachfolgern 2509 und 2511 bessert der Hersteller beim Wegdriften vom Ausgangsbild und bei der Konsistenz nach [3]; beides entscheidet nach Kriterium 3 über ein Bearbeitungsergebnis. Damit gleichauf mit Stable Diffusion 3.5 Large (3, gesetzt) und unter Flux 2 Dev (4, vor diesem Maßstab gesetzt). |
| Qwen 2511 Multi-Image Fusion (`qwen_2511_multi`) | 4 | Das Grundmodell Qwen-Image-Edit-2511 erschien im Dezember 2025. Der Hersteller nennt „notably better consistency“ gegenüber 2509, weniger Drift und das Zusammenführen von Personen aus zwei Bildern zu einem Gruppenbild [3]. Das ist die Aufgabe, für die die Plattform es einsetzt. Die Verkürzung ist dieselbe wie bei Qwen Image Edit Lightning (4 Schritte, FP8) [2]. Damit gleichauf mit Flux 2 Dev (4) und unter Gemini 3 Pro Image (5, vor diesem Maßstab gesetzt). |
| Stable Audio 3 (`stableaudio_open`) | 3 | Stable Audio 3 medium erschien im Mai 2026 und hat rund 1,4 Mrd. Parameter. Es folgt auf Stable Audio Open 1.0 (Paper Juli 2024, Stufe 2 gesetzt) und erzeugt Musik und Geräusche von variabler Länge bis zu mehreren Minuten; das adversariale Nachtraining soll „accelerate inference and improve generation quality“ [4]. Die Plattform lässt es mit 8 Schritten und CFG 1 laufen, wie das Modell ausgelegt ist. Einen Zahlenvergleich mit Stable Audio Open 1.0 veröffentlicht der Hersteller nicht [4]. Die Quellen nennen weder Gesang noch Liedtexte; HeartMuLa (4) erzeugt Musik mit Gesang aus Liedtexten. Damit zwischen Stable Audio Open 1.0 (2) und HeartMuLa (4). |
| Hunyuan3D-2 (`hunyuan3d_text_to_3d`) | 2 | Hunyuan3D-2 erschien im Januar 2025 und erzeugt Form und Textur; der Hersteller beansprucht beim Erscheinen einen Vorsprung vor kommerziellen und offenen Vergleichsmodellen [5]. Als Vorschlag für den unteren Anker bei 3D gilt Point-E (Dezember 2022): Es erzeugt Punktwolken ohne Oberfläche und bleibt nach eigener Aussage „short of the state-of-the-art in terms of sample quality“ [6]. Hunyuan3D-2 liegt darüber. Die Plattform lässt Version 2.0 laufen; der Hersteller hat im Juni 2025 Version 2.1 mit physikalisch basierten Materialien an Stelle der RGB-Textur veröffentlicht [7]. Die gesetzte Obergrenze ist 2. |

Quellen:
[1] https://huggingface.co/Qwen/Qwen-Image-Edit (Paper arXiv:2508.02324)
[2] https://github.com/ModelTC/Qwen-Image-Lightning
[3] https://huggingface.co/Qwen/Qwen-Image-Edit-2511; https://qwen.ai/blog?id=qwen-image-edit-2511
[4] Evans u. a., „Stable Audio 3“, arXiv:2605.17991 (18.05.2026); https://huggingface.co/stabilityai/stable-audio-3-medium
[5] https://huggingface.co/tencent/Hunyuan3D-2
[6] Nichol u. a., „Point-E“, arXiv:2212.08751 (16.12.2022)
[7] https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1

## Offen

- Die Kriterien und die Auslegung der Anker, die vorläufig gelten.
- Der obere Anker je Medium, mit einem Produkt und Datum benannt.
- Der untere Anker für Video und 3D, mit einem Modell benannt; die Beispiele für Bild und Klang sind ein Vorschlag ohne Quelle.
- Die Stufen, die vor diesem Maßstab gesetzt sind, nach ihm geprüft.
- Für p5.js und Tone.js die Frage, ob der Maßstab gilt: Was diese Configs liefern, ist Code, den ein Sprachmodell schreibt.
