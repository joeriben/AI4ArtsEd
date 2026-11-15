# 27 Tokenizer — `/latent-lab/tokenization`

Used 2026-11-03, 00:06–00:22 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/tokenization` (sidebar "Tokenizer", tooltip "Token cost by language"). Preparing column: Example prompts select (two entries), the sentence field prefilled with "A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.", a field "A single word to compare" prefilled with "House", and "Tokenizer" chips: Qwen3-4B (tooltip "The text model of this platform."), Llama 3.2, Gemma 2, Phi 3.5 (each "Another text model. It cuts differently."), XLM-RoBERTa ("Trained on many languages at once."), CLIP ("The text reader of the picture models. Its window is only 77 tokens wide."); the active chip's tooltip stands as a line under the chips. A note: "A token is a piece of text. The tokenizer determines how a text is cut. It was built on certain languages." and "More tokens means two things: the model's window fills up faster, and the computing time rises. That also means higher cost and higher energy use for the same work by the model." Right: "Your sentence, cut into tokens" with numbered chips, a line "22 tokens · Vocabulary: 151,669 tokens · Window: 40,960 tokens", a bar "<0,1 % of the window", and a heading "The same sentence in the eleven languages of this platform" with "The comparison starts in the bar above. It translates your sentence into eleven languages and cuts each version." The run button is the play triangle in the header.
2. Typed "Haus", then "дом", then "집" into the sentence field and clicked each of the six chips in turn; the cut appeared within a second each time.
3. Typed the three words into "A single word to compare" as well: nothing visible changed.
4. Typed a sentence of 92 tokens (a school morning, one long sentence) and compared Qwen3-4B with CLIP.
5. Pressed the play button at 00:15:37 for the eleven-language comparison: the explanatory line vanished and the button showed as running. (Result: see 3.)

Runs: one translation run; every cut is instant.

## 2. What the controls did

- Sentence field: every keystroke re-cuts the text for the active chip.
- Chips: switch the tokenizer; the count, the vocabulary size, the window and the bar change with it.
- "A single word to compare": no visible effect.
- Play button: starts the eleven-language comparison.
- Copy / Paste / Translate to English / Delete on the field; Hide column; Help.

## 3. What came out

- The house sentence in Qwen3-4B: 22 tokens; "farmland" is "␣far" + "mland"; vocabulary 151,669; window 40,960; under 0.1 % of the window.
- "Haus": Qwen3-4B "H" + "aus" (2 tokens); Llama 3.2 "H" + "aus" (2; vocabulary 128,256, window 131,072); Gemma 2 "Haus" (1; 256,000; 8,192); Phi 3.5 "Haus" (1; 32,011; 131,072); XLM-RoBERTa "Haus" (1; the line showed 32,011 and 131,072, the same numbers as Phi 3.5, which it showed differently a moment later); CLIP "haus" (1; 49,408; 77; 1.3 % of the window).
- "дом": Qwen3-4B "д" + "ом" (2); Llama 3.2 1; Gemma 2 1; Phi 3.5 "до" + "м" (2); XLM-RoBERTa 1 (250,002; window 514; 0.2 %); CLIP 4 tokens, shown as "д", "д", "ом", "м" (5.2 % of the window).
- "집": Qwen3-4B 1; Llama 3.2 1; Gemma 2 1; Phi 3.5 4 tokens, all four shown as "집"; XLM-RoBERTa 1; CLIP 2, both shown as "집".
- The long sentence: Qwen3-4B 92 tokens, 0.2 % of its window; CLIP 92 tokens, "119 % of the window", the bar full-length and green. CLIP lowercases every word and shows no leading-space marks; Qwen3-4B shows "␣" before each word.
- Eleven-language comparison: the translation of the paragraph into ten languages is a language-model run, and the button shows its running state until the result arrives. Token counts of the same paragraph: English 92, Deutsch 148, Español 157, Français 167, Türkçe 181, 繁體中文 276, 한국어 279, العربية 297, Українська 427, Български 436; עברית shows a "·" and no count. English, the language the tokenizer was built around, is the cheapest; Ukrainian and Bulgarian cost 4.6 times as many tokens for the same text. The word field feeds the same comparison: "집" (house) came back as Deutsch "haus" 1 piece, Español "casa" 1, Français "maison" 1, Türkçe "ev" 1, English "집" 2 (left untranslated), 繁體中文 "家" 2, 한국어 "집" 2, العربية 3 pieces (ب ي ت), עברית 6 (ב ב י י ת ת, each letter twice), Български 6 (къща in pieces), Українська 9 (будинок as byte pieces). The Latin-script words are one token; the Cyrillic word is nine.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The pieces of one character of another script appear as repeated letters ("д д ом м", "집 집 집 집"); nothing says that these are bytes of one character.
- "A single word to compare" does nothing visible.
- The vocabulary and window numbers lagged one chip behind once (XLM-RoBERTa shown with Phi 3.5's numbers).
- The 119 % bar is green and full; nothing says that CLIP cuts the prompt off after the 77th token.
- The play button's purpose is only in the sentence under the right-hand heading.

## 6. What the help text should tell a user

Type any text and the chips show how the chosen model cuts it into tokens, each piece numbered; the line under the pieces gives the count, the model's vocabulary and its window, and the bar how much of the window the text fills. Switch the chips to compare models: a word of another script may fall into several pieces, and a piece shown as a repeated letter is a fragment of one character. CLIP's window is 77 tokens; whatever stands beyond it does not reach the picture model. The play button translates the sentence into the platform's eleven languages and cuts each version, so that the cost of a language can be compared.

## 7. Use possibilities, action-oriented

- One sentence in the languages of the group; count the tokens per model and language in a table.
- A long image prompt in CLIP: find the 77th token and shorten the prompt to fit.
- Words of three scripts in Phi 3.5 and Qwen3-4B; note which model needs more pieces.
- The same word with and without a capital letter in CLIP and in Qwen3-4B.

## 8. Teaching scenarios

**S1 — Count the tokens** (formal, languages or computer science, grades 7–10, 45 min). Pupils write one sentence in every language present in the class, cut it with two models and fill a table; the class reads the note's two sentences on window, time and energy and discusses whose language is cheap. Sequence: 10 min sentences; 15 min table; 20 min discussion. Subject link: writing systems, cost. Uncertainty: the eleven-language run is a model run; the hand-typed route needs none.

**S2 — Seventy-seven** (formal, art or media, grades 9–12, 45 min). Pupils paste their longest image prompt into the field, switch to CLIP, read the percentage, and cut the prompt until it fits; then they decide what they removed. Subject link: writing for a picture model.

**S3 — One character, four pieces** (non-formal, media workshop, age 14+, 90 min). Participants type words of scripts they know (Cyrillic, Korean, Arabic, emoji) into Phi 3.5, CLIP and Qwen3-4B, collect the cases where a character becomes several pieces, and look up what a byte-level tokenizer does. Subject link: encodings. Uncertainty: the repeated-letter display needs the facilitator's explanation.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1, S3: the model reads pieces, not words.
- Engage 5 Basic — "Learners recognise that computers and AI systems require resources to function." S1: the note's sentence on computing time and energy per token, read on the surface.
- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." S2: the 77-token window of CLIP as a stated constraint.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S1: the token count per language in the table and the note's sentences on window, time and energy: one vocabulary, decided in design, gives speakers of some languages more tokens, less window and higher cost for the same sentence. The framework's classroom example asks how and why a system performs differently across groups; S1's discussion of whose language is cheap is that question.

**(b) Mutatis mutandis**


**Non-fits**: Engage 1, 3, 4, 7, Manage 1–4, Shape 2, 3, 4, Create 1–4.
