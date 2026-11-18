---
id: gal-et-al-2022-an-image-is-worth-one-word-textual-inversion
titel: "An Image is Worth One Word: Personalizing Text-to-Image Generation using Textual Inversion"
autor: "Rinon Gal, Yuval Alaluf, Yuval Atzmon, Or Patashnik, Amit H. Bermano, Gal Chechik, Daniel Cohen-Or"
jahr: 2022
quelle: "Preprint, under review (Tel-Aviv University / NVIDIA)"
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2208.01618"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:12:12.392464+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# An Image is Worth One Word: Personalizing Text-to-Image Generation using Textual Inversion

## PROFIL

The paper "An Image is Worth One Word: Personalizing Text-to-Image Generation using Textual Inversion" was written by Rinon Gal, Yuval Alaluf, Yuval Atzmon, Or Patashnik, Amit H. Bermano, Gal Chechik and Daniel Cohen-Or, of Tel-Aviv University and NVIDIA, as a research contribution to the field of text-guided image synthesis. It introduces the task of personalized text-to-image generation and argues that a single learned embedding vector — a pseudo-word in a frozen text encoder's embedding space — suffices to capture a user-provided concept (an object, pet, or artistic style) from 3–5 example images, without retraining or fine-tuning the generative model; the authors call this optimization process Textual Inversion. The paper first positions the work against literatures on text-guided synthesis (DALL-E, LDM, Imagen, GLIDE, VQGAN-CLIP), GAN inversion, diffusion-based inversion, and personalization (notably PALAVRA, whose discriminative objectives fail to capture fine detail). It then presents the method, implemented over Latent Diffusion Models: a placeholder string's embedding is optimized with a reconstruction objective while the text encoder and denoiser remain fixed. Subsequent sections report qualitative comparisons against human-caption and image-prompt baselines, applications to style transfer, concept composition, bias reduction, and localized editing with Blended Latent Diffusion; a quantitative analysis with CLIP-based reconstruction and editability metrics plus human evaluations, showing a distortion–editability tradeoff; and a discussion of limitations (semantic rather than precise shape capture, roughly two hours per concept), social impact (forgery, inherited biases, copyright of artists' styles), and conclusions. Supplementary materials cover bipartite DDIM-inversion, pivotal tuning, the effect of training set size, additional galleries, and the training prompt templates. For arts education, the paper is usable in disciplines dealing with generative AI, digital media art, and design: it explains how personal objects and artistic styles can be composed into natural-language prompts for creative work, rapid prototyping, and product design, while also providing material for critical discussion of bias and copyright in AI-generated art.

## WISSEN

### Purpose and Thesis (p. 1–3)

This paper introduces the task of **personalized text-to-image generation**: enabling a frozen, pre-trained text-to-image model to generate novel scenes of specific, user-provided concepts (a personal object, pet, or artistic style) guided by natural language. The authors' thesis is that a single new "word" — a learned embedding vector in the text encoder's embedding space — is sufficient to capture a unique concept in its fine visual detail, using only 3–5 example images, without retraining or fine-tuning the generative model itself. They call this optimization process "Textual Inversion." The work was conducted by Rinon Gal, Yuval Alaluf, Yuval Atzmon, Or Patashnik, Amit H. Bermano, Gal Chechik and Daniel Cohen-Or (Tel-Aviv University and NVIDIA).

The motivating example is the scene from 'Titanic' in which Rose asks Jack to "draw me like one of your French girls" — a request combining a style, a composition, and a specific unique subject. The paper asks how a user could make an analogous request to a text-to-image model, e.g., to place a cherished childhood toy in a new scene. The authors argue that re-training is prohibitively expensive and fine-tuning on few examples causes catastrophic forgetting, while adapter-style approaches still risk losing prior knowledge. Their solution leaves the model untouched and instead "injects" the concept into its vocabulary.

The stated contributions are: (1) introducing the personalization task; (2) presenting Textual Inversion — finding pseudo-words in a text encoder's embedding space that capture both high-level semantics and fine visual details; (3) showing that the textual embedding space exhibits a distortion–editability tradeoff (as in GAN inversion), and that their approach occupies an appealing point on that curve; and (4) demonstrating higher visual fidelity and more robust editing than human-caption baselines.

### Related Work (p. 2–4)

The authors position their work against four literatures:

- **Text-guided synthesis**: conditional GANs, autoregressive models (DALL-E), and diffusion models (LDM, Imagen, GLIDE). Unlike approaches that train new models or perform test-time CLIP-guided optimization (VQGAN-CLIP, CLIP-Guided Diffusion), they expand a frozen model's vocabulary.
- **GAN inversion**: optimization-based vs. encoder-based inversion of images into latent spaces. They follow the optimization approach because it adapts better to unseen concepts.
- **Diffusion-based inversion**: DDIM inversion (Dhariwal & Nichol) and DALL-E 2's bipartite process invert a given *image*; this work instead inverts a user-provided *concept*.
- **Personalization**: most relevantly PALAVRA (Cohen et al., 2022), which finds pseudo-words in CLIP's embedding space for retrieval and segmentation. Because PALAVRA's objectives are discriminative, it fails to capture the detail needed for plausible reconstruction or synthesis in new scenes.

### Method: Textual Inversion (p. 4–5)

The method is implemented over **Latent Diffusion Models (LDMs)**, which consist of (1) an autoencoder mapping images to spatial latents and back, and (2) a diffusion model trained to denoise latents, conditioned via a text encoder cθ(y). The authors use the publicly available 1.4-billion-parameter LDM text-to-image model pre-trained on LAION-400M, with a BERT text encoder.

Key idea: in the text encoder, each input word/sub-word is converted to a token and then replaced by a unique embedding vector. The authors designate a placeholder string S* for the new concept and replace its embedding vector with a new, learned embedding v*, found by direct optimization. Given a small set of 3–5 images of the concept, they minimize the LDM loss over those images while keeping both cθ and the denoiser εθ fixed, conditioning on randomly sampled neutral templates derived from CLIP ImageNet templates (e.g., 'A photo of S*', 'A rendition of S*'; full list in supplementary, p. 26). Because this is a reconstruction objective, the learned embedding is motivated to capture fine visual details unique to the concept.

Implementation details: word embeddings initialized from a single-word coarse descriptor (e.g., 'sculpture', 'cat'); 2× V100 GPUs, batch size 4; base learning rate 0.005, scaled by GPU count and batch size to an effective rate of 0.04; 5,000 optimization steps. Fewer steps or higher learning rates can help some concepts.

### Qualitative Comparisons and Applications (p. 6–11)

- **Image variations (p. 6–7)**: Compared against LDM and DALL-E 2 guided by human captions (collected via Mechanical Turk; 10 captions per concept — five short ≤12 words, five long ≤30 words) and DALL-E 2 with image prompts. Human captions capture prominent features but miss fine details (e.g., the teapot's color patterns); some objects (a skull mug) are nearly indescribable in words. DALL-E 2 with image prompts works for well-known objects (Aladdin's lamp) but struggles with unique personalized objects. The authors' method captures finer details with a single word embedding, though outputs remain variations rather than exact copies.
- **Text-guided synthesis (p. 7–8)**: Pseudo-words can be composed into new sentences; the frozen model jointly reasons over new concepts and its prior knowledge (e.g., a learned bowl can contain food; the Furby's bird-like head and crown persist while its palette adapts to an album-cover prompt).
- **Comparison to personalization baselines (p. 8)**: Against PALAVRA (used with VQGAN-CLIP and CLIP-Guided Diffusion) and CLIP-guided joint optimization. PALAVRA images contain prompt elements but show visual corruption; CLIP-guided methods look natural but fail to generalize to new texts and require expensive per-creation optimization, whereas a learned pseudo-word is reusable.
- **Style transfer (p. 9)**: Providing images sharing a style and training with prompts of the form 'A painting in the style of S*' yields pseudo-words for styles (image credits: @QinniArt, @David Revoy). This differs from traditional style transfer in that content need not be preserved.
- **Concept compositions (p. 9–10)**: Multiple learned pseudo-words can be used in one prompt, but the model struggles with relations between concepts (e.g., placing two side-by-side), hypothesized to stem from single-concept training.
- **Bias reduction (p. 9–10)**: Text-to-image models inherit biases from their internet-scale training data. The DALL-E 2 system card (Mishkin et al., 2022) reports that its baseline model tends to produce images of people that are white-passing and male-passing for the prompt 'A CEO', and that results for 'wedding' default to Western traditions and heterosexual couples. In Figure 8, the authors highlight the bias encoded in the word 'Doctor' and show it can be reduced — increasing perceived gender and ethnic diversity — by learning a new embedding from a small, more diverse image set.
- **Downstream applications (p. 10–11)**: Pseudo-words work with Blended Latent Diffusion for localized, mask-based image editing without model modification.
- **Curation (p. 10)**: Results are partially curated — 16 candidates per prompt (6 for DALL-E 2), best manually selected; uncurated galleries are in the supplementary.

### Quantitative Analysis (p. 11–13)

**Metrics**: (1) *Reconstruction* — average pairwise CLIP-space cosine similarity between 64 images generated with 'A photo of S*' and the training set; (2) *Editability (text-similarity)* — CLIP similarity between the average embedding of 64 samples (50 DDIM steps) and the text prompt with S* omitted, across prompts of varying difficulty ('A photo of S* on the moon', 'An oil painting of S*', 'Elmo holding a S*').

**Evaluation setups** (p. 12):
- Extended latent spaces: 2-word and 3-word embeddings (following Abdal et al.).
- Progressive extensions: a second vector introduced after 2,000 steps, a third after 4,000 (following Tov et al.).
- Regularization: L2 distance to the embedding of a coarse descriptor.
- Per-image tokens: a universal placeholder S* plus per-image placeholders {S_i}, in sentences 'A photo of S* with S_i', jointly optimized so shared information goes into S* and per-image details into S_i.
- Human captions (short and long).
- Reference baselines: 'Image Only' (training set as output) and 'Prompt Only' (generation without the pseudo-word).
- Textual Inversion itself, plus High-LR (2e-2) and Low-LR (1e-4) variants.
- Supplementary setups: pivotal tuning and DALL-E 2's bipartite inversion.

**Results** (p. 12–13): (1) Reconstruction quality of the method matches sampling random training images; (2) the single-word model achieves comparable reconstruction and considerably better editability than all multi-word baselines; (3) baselines trace a distortion–editability tradeoff — embeddings closer to the true word distribution are more editable but less faithful, and vice versa; the single-embedding model can be moved along this curve by changing the learning rate; (4) human captions fail both at likeness and editability, hypothesized to relate to the selective-similarity property (Paiss et al., 2022), where models focus on a subset of semantic tokens. A caveat: CLIP-based metrics are less sensitive to shape preservation.

**Human evaluations** (p. 13): Two questionnaires (ranking similarity to training images; ranking similarity to a context text), 600 responses each (1,200 total). Results align with the CLIP-based metrics, showing the same tradeoff and the limitations of captioning.

### Limitations, Social Impact and Conclusions (p. 13–14)

**Limitations**: the method captures the 'semantic' essence of a concept rather than precise shapes; learning one concept takes roughly two hours, which might be shortened in future by training an encoder mapping image sets directly to embeddings.

**Social impact**: risks include more convincing forged images of non-public individuals (though identity preservation is currently insufficient for this), inherited biases (gender, racial, Western-tradition biases in prompts like 'wedding'), and potential copyright infringement through learning artists' styles without consent — though the authors also note opportunities such as artists licensing their style or rapid prototyping.

**Conclusions**: Textual Inversion inverts user concepts into pseudo-words in a frozen text-to-image model's embedding space, enabling intuitive natural-language composition. Implemented over LDM, the approach is not architecture-dependent and should transfer to larger models. The authors hope it paves the way for personalized generation in artistic inspiration and product design.

### Supplementary Materials (p. 19–26)

- **Additional inversion approaches (p. 19–20)**: *Bipartite DDIM-inversion* — freezing the noise map x_T while changing the conditioning text — fails with LDM's typical guidance scales (5–10): the object's structure is not maintained through prompt changes, and at lower guidance scales prompt alignment is poor. The authors note state-of-the-art models use much lower guidance scales (~2), giving hope for better shape preservation there. *Pivotal tuning* — fine-tuning the generator after learning a pseudo-word — improves shape preservation but causes severe collapse of editing at high guidance scales; further investigation is left to future work.
- **Effect of training set size (p. 21)**: Sweeping from 1 to 25 images on the headless sculpture concept shows that more images push embeddings farther from real word embeddings, harming editability; the method operates best with 5 images.
- **Additional results (p. 21–25)**: galleries of text-guided synthesis (e.g., 'S* Starry Night', 'A mossy S*', 'S* in Minecraft', 'A poster for the movie "The teapot" starring S*'), uncurated 'A photo of S*' variations, and failure cases such as difficult relational prompts.
- **Training prompt templates (p. 26)**: the full list of 25 templates used during optimization, e.g., 'a rendering of a S*.', 'a cropped photo of the S*.', 'a dark photo of the S*.', 'a close-up photo of a S*.', 'a rendition of the S*.', 'a photo of the weird S*.', 'a photo of the large S*.'

### Figures (p. 1–25)

*Image 1 (p. 1):* — This is a two-row diagram in a document showing input photographs on the left and generated images on the right, connected by arrows. In the top row, four photos of a dark seated statue labeled “Input samples” with “invert” and “S*” lead to outputs captioned “An oil painting of S*”, “App icon of S*”, “Elmo sitting in the same pose as S*”, and “Crochet S*”. In the bottom row, three photos of a colorful striped cat figurine labeled “Input samples” with “invert” and “S*” lead to outputs captioned “Painting of two S* fishing on a boat”, “A S* backpack”, “Banksy art of S*”, and “A S* themed lunchbox”.

*Fig. 2 (p. 4):* Outline of the text-embedding and inversion process. A string containing our placeholder word is first converted into tokens ( i.e . word or sub-word indices in a dictionary). These tokens are converted to continous vector representations (the 'embeddings', v ). Finally, the embedding vectors are transformed into a single conditioning code c θ ( y ) which guides the generative model. We optimize the embedding vector v ∗ associated with our pseudo-word S ∗ , using a reconstruction objective. — This is a schematic diagram of a text-conditioning and image-generation pipeline. On the left, a yellow box reading “A photo of S_*” connects downward through green “Tokenizer” and “Text Transformer” boxes and a blue “Embedding Lookup” box, all inside a “Text Encoder” area, with arrows labeled 508, 701, 73, (*) and v_508, v_701, v_73, v_*; a padlock icon sits on the Text Transformer. A central blue panel lists embedding rows v_0, v_73, v_508, v_701 and a final row v_* filled with “????”, also with a padlock, and an arrow marked c_θ(y) runs from the Text Encoder to the right. On the right, a locked green “Generator” column shows clock images rising to a clearer clock at the top, while an “Input Sample” clock image sits above a “Noised Sample” column of progressively blurred clock images, with dashed arrows pointing from the Noised Sample column toward the Generator column. _(Lettering in the image, read by the image model, not confirmed: “A photo of S_*”)_

*Image 3 (p. 6):* — This is a comparison figure from a document showing a grid of images organized into three columns labeled "Skull Mug", "Teapot", and "Aladdin Lamp" and six rows labeled "Input samples", "Ours", "DALLE-2 (Image Inputs)", "DALLE-2 (Long Captions)", "LDM (Long Captions)", and "LDM (Short Captions)". Each cell in the grid contains three images, and text captions appear below several rows, including "A photo of S*", "A mug having many skulls at the bottom and sculpture of a man at the top of it.", "A tea pot, with green, red, blue, yellow, an apple with leaves and a lemon with leaves.", "An oil lamp, like Aladdin's lamp, in gold metal, with a design around the pedestal base and lid.", "Mug or vase featuring grouchy faced", "A colorful tea pot having leaf prints", and "A gold genie lamp with a long spout and slim body".

*Image 4 (p. 7):* — The picture is a printed figure arranged as a grid of five rows; each row shows small photographs labeled “Input samples” on the left, an arrow, and four larger images with captions underneath. The five input objects are an ornate brown object, a small bird, a colorful cartoon bird, a bowl, and a teapot, and the captions use “S.” for that object, including “S. sports car,” “S. made of lego,” “S. onesie,” “da Vinci sketch of S.,” “Watercolor painting of S. on a branch,” “A house in the style of S.,” “Grainy photo of S. in angry birds,” “S. made of chocolate,” “A mosaic depicting S.,” “Death metal album cover featuring S.,” “Masterful oil painting of S. hanging on the wall,” “An artist drawing a S.,” “A photo of S. full of cashew nuts,” “A mouse using S. as a boat,” “A photo of a S. mask,” “Ramen soup served in S.,” “A carpet with S. embroidery,” “A S. stamp,” “S. fedora,” and “Felt S.”. Some small text inside individual generated images, such as on the album cover and stamp, is not fully legible. _(Lettering in the image, read by the image model, not confirmed: “Watercolor painting of S. on a branch,”, “Death metal album cover featuring S.,”, “Masterful oil painting of S. hanging on the wall,”)_

*Image 5 (p. 8):* — This is a figure displaying a grid of images with two columns labeled "Clock" and "Mug" and six rows labeled "Input samples", "PALAVRA (VQGAN+CLIP)", "PALAVRA (Guided Diffusion)", "VQGAN+CLIP (Text + Image Loss)", "Guided Diffusion (Text Loss + Init Image)", and "Ours". Each cell contains a photograph of a clock or a mug shown in different styles, backgrounds, and contexts. At the bottom of the figure are text captions reading "A photo of $S_*$", "A photo of $S_*$ on the beach", "A photo of $S_*$ on the moon", and "Elmo holding a $S_*$". _(Lettering in the image, read by the image model, not confirmed: "A photo of $S_*$")_

*Fig. 6 (p. 9):* The textual-embedding space can represent more abstract concepts, including styles. This allows us to discover words which can be used for style-guided generation. Image credits: @QinniArt (top), @David Revoy (bottom). Image reproduction authorized for non-commercial use only. — This is a composite diagram of digital images rather than a single photograph. At the lower left, the label “Input samples” sits beside two groups of small artworks: four colorful stylized portraits in the upper group and three dark-toned artworks in the lower group. Arrows lead from each group to four generated pictures on the right, arranged in two rows showing a Paris street with the Eiffel Tower, a corgi, a black hole, and Times Square, with the top row in bright multicolor and the bottom row in dark, muted tones. Under the four columns are the captions “The streets of Paris in the style of S∗.”, “Adorable corgi in the style of S∗.”, “Painting of a black hole in the style of S∗.”, and “Times square in the style of S∗.”

*Image 7 (p. 10):* — The picture is a composite figure from a document, arranged in two rows of small image panels. The top row shows four groups of source images labeled S_style (drawn female portraits), S_clock (photographs of alarm clocks), S_cat (photographs of small cat figurines), and S_craft (photographs of colorful pipe-cleaner creatures). The bottom row shows six generated images captioned “Photo of S_clock in the style of S_style,” “Photo of S_cat in the style of S_style,” “Photo of S_craft in the style of S_style,” “Photo of S_clock in the style of S_cat,” “Photo of S_clock in the style of S_craft,” and “Photo of S_cat in the style of S_craft.” _(Lettering in the image, read by the image model, not confirmed: “Photo of S_clock in the style of S_style,”, “Photo of S_cat in the style of S_style,”, “Photo of S_clock in the style of S_craft,”)_

*Image 8 (p. 10):* — The image is a document figure made up of two side-by-side grids of portrait photographs, each grid arranged in three rows of five cells. The cells show people in medical attire—white lab coats or blue scrubs, often with a stethoscope—against indoor, clinical-looking backgrounds. Beneath the left grid is the legible caption “A stock photo of a doctor” (Base model), and beneath the right grid is the legible caption “A photo of S_*” (Ours). _(Lettering in the image, read by the image model, not confirmed: “A photo of S_*”)_

*Fig. 9 (p. 11):* Our words can be used with downstream models that build on LDM. Here, we perform localized image editing using Blended Latent Diffusion (Avrahami et al., 2022a) — This is a figure from a document arranged as a three-row grid of images. The top row, labeled “Input Samples,” shows several photographs of a small green seated statue on the left and of a striped cat figurine on the right. The middle row, labeled “Target Image With Mask,” shows four target images—a Mona Lisa painting, a black-and-white photo of workers on a beam, a moon-landing photo, and a man holding a phone—each with a translucent purple mask over one region. The bottom row, labeled “Output Image,” shows the same four scenes with the masked region replaced by the statue or the cat figurine, under captions reading “An oil painting of S*,” “A black and white photo of S*,” “A S*,” and “A S*.”

*Fig. 10 (p. 13):* Qualitative evaluation results. (a) CLIP-based evaluations. The single-word model (ours) represents an appealing point on the distortion-editability curve, and can be moved along it by changing the learning rate. (b) User study results. These results portray a similar distortion-editability curve, and demonstrate that the CLIP-based results align with human preference. User study error bars are 95% confidence intervals. — The image contains two side-by-side scatter plots labeled (a) and (b). Plot (a) has x-axis “Text Similarity” and y-axis “Image Similarity,” with colored points labeled “Image only,” “Prompt only,” “Long captions,” “Short captions,” “3-words,” “2-words,” “w/Progressive,” “High-LR,” “Per-image token,” “Ours,” “Low-LR,” and “w/Regularization.” Plot (b) has x-axis “Text Similarity Rank” and y-axis “Image Similarity Rank,” and shows points with elliptical error bars labeled “3-words,” “Ours,” “Short captions,” “Long captions,” and “w/Regularization.” _(Lettering in the image, read by the image model, not confirmed: “Text Similarity”, “Image Similarity,”, “Image only,”, “Prompt only,”, “Short captions,”, “3-words,”, “2-words,”, “w/Progressive,”, “High-LR,”, “Per-image token,”, “Low-LR,”, “w/Regularization.”, “Text Similarity Rank”, “Image Similarity Rank,”, “3-words,”, “Short captions,”, “w/Regularization.”)_

*Image 11 (p. 20):* — This is a figure from a document that compares two image-generation methods. At the top, under the label “Input Samples”, are three photographs of a dark seated sculptural figure on different surfaces. Below, two columns headed “Bipartite Inversion” and “Pivotal Tuning” show a “Reconstruction” row followed by rows labeled “s = 1”, “s = 2”, and “s = 5”; the left column is captioned “A painting of S” and the right column “A watercolor painting of S”, with the left results becoming increasingly landscape-like as s grows while the right results remain watercolor renderings of the figure.

*Image 12 (p. 21):* — This is a scatter plot chart with the horizontal axis labeled "Text Similarity" and the vertical axis labeled "Image Similarity." Several data points are marked with text labels, including "Image only" in the upper left, "Long captions" and "Short captions" in the middle-right area, and "Prompt only" in the lower right. Six additional points are labeled with the numbers 1, 5, 10, 15, 20, and 25, located in the upper right portion of the plot. _(Lettering in the image, read by the image model, not confirmed: "Text Similarity", "Image Similarity.", "Long captions", "Short captions")_

*Image 13 (p. 22):* — The picture is a multi-panel figure arranged as five rows. In each row, four small photographs sit under the label “Input samples” on the left, followed by an arrow and four larger images on the right, each with a caption below. The rows show houses, an elephant, a curved tusk, a unicorn, and a teapot as inputs, and the outputs are captioned with prompt-like lines containing “S*”, for example “The Scream in the style of S*.”, “S*, Starry Night”, “Painting of S*, in the style of Monet”, “S*, in Minecraft”, and “S*, Death Star”.

*Fig. 14 (p. 23):* Uncurated samples of object variations created using the prompt 'A photo of S ∗ '. — The image is a screenshot of a figure from a document, arranged in six horizontal rows. Each row shows a small set of “Input samples” photographs of an object on the left, an arrow, and a larger grid of generated photographs of that object beneath the caption “A photo of S*.” The objects shown from top to bottom are a speckled bird figurine, a patterned bowl, a cat figurine, a green seated statue, a white bird figurine, and a decorated turtle figurine.

*Image 15 (p. 24):* — This figure displays reference photographs on the left and multiple grids of generated images on the right. On the left, three groups of small photographs are labeled "S_cat", "S_clock", and "S_bird". On the right, six rows of generated artwork appear with captions reading "Banksy art of S_cat", "Painting of a S_cat riding a dragon", "Painting of two S_cat fishing on a boat", "A S_cat themed lunchbox", "A painting of S_cat holding a S_clock", and "Ukiyo-e painting of S_bird". _(Lettering in the image, read by the image model, not confirmed: "S_cat", "S_clock", "S_bird")_

*Image 16 (p. 25):* — This is a composite figure made of grids of small computer-generated images, with text captions under several rows. The upper rows show dark teal crocheted seated figures labeled “S_sculpture” and “Crochet S_sculpture,” followed by black-and-white ink-wash and sketch versions captioned “S_sculpture ink wash calligraphy” and “A black and white sketch of S_sculpture.” The middle rows show colorful spider-like craft objects labeled “S_craft,” bright backpacks captioned “A S_craft backpack,” and vivid paintings captioned “A painting of S_craft invading from space.” The bottom row shows anime-style portraits labeled “S_style” next to abstract purple, pink, and blue images; some small text inside the upper-right thumbnails is not legible. _(Lettering in the image, read by the image model, not confirmed: “S_sculpture”, “S_craft,”, “S_style”)_

<!-- quelle: An Image is Worth One Word: Personalizing Text-to-Image Generation using Textual Inversion (p. 1–26) -->

## LITERATUR

<!-- quelle: References (p. 15–18) -->

- Rameen Abdal, Yipeng Qin, and Peter Wonka. Image2stylegan: How to embed images into the stylegan latent space? In Proceedings of the IEEE/CVF International Conference on Computer Vision , pp. 4432-4441, 2019.
- Rameen Abdal, Yipeng Qin, and Peter Wonka. Image2stylegan++: How to edit the embedded images? In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition , pp. 8296-8305, 2020.
- Rameen Abdal, Peihao Zhu, John Femiani, Niloy J Mitra, and Peter Wonka. Clip2stylegan: Unsupervised extraction of stylegan edit directions. arXiv preprint arXiv:2112.05219 , 2021.
- Eirikur Agustsson, Fabian Mentzer, Michael Tschannen, Lukas Cavigelli, Radu Timofte, Luca Benini, and Luc Van Gool. Soft-to-hard vector quantization for end-to-end learned compression of images and neural networks. arXiv preprint arXiv:1704.00648 , 3, 2017.
- Yuval Alaluf, Omer Tov, Ron Mokady, Rinon Gal, and Amit H. Bermano. Hyperstyle: Stylegan inversion with hypernetworks for real image editing, 2021.
- Fernando Amat, Ashok Chandrashekar, Tony Jebara, and Justin Basilico. Artwork personalization at netflix. In Proceedings of the 12th ACM Conference on Recommender Systems , RecSys '18, pp. 487-488, New York, NY, USA, 2018. Association for Computing Machinery. ISBN 9781450359016. doi: 10.1145/ 3240323.3241729. URL https://doi.org/10.1145/3240323.3241729 .
- Omri Avrahami, Ohad Fried, and Dani Lischinski. Blended latent diffusion. arXiv preprint arXiv:2206.02779 , 2022a.
- Omri Avrahami, Dani Lischinski, and Ohad Fried. Blended diffusion for text-driven editing of natural images. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pp. 1820818218, 2022b.
- Omer Bar-Tal, Dolev Ofri-Amar, Rafail Fridman, Yoni Kasten, and Tali Dekel. Text2live: Text-driven layered image and video editing. arXiv preprint arXiv:2204.02491 , 2022.
- David Bau, Hendrik Strobelt, William Peebles, Jonas Wulff, Bolei Zhou, Jun-Yan Zhu, and Antonio Torralba. Semantic photo manipulation with a generative image prior. 38(4), 2019. ISSN 0730-0301. doi: 10.1145/ 3306346.3323023. URL https://doi.org/10.1145/3306346.3323023 .
- David Bau, Hendrik Strobelt, William Peebles, Jonas Wulff, Bolei Zhou, Jun-Yan Zhu, and Antonio Torralba. Semantic photo manipulation with a generative image prior. arXiv preprint arXiv:2005.07727 , 2020.
- Soulef Benhamdi, Abdesselam Babouri, and Raja Chiky. Personalized recommender system for e-learning environment. Education and Information Technologies , 22(4):1455-1477, 2017.
- Chen Cao, Tomas Simon, Jin Kyu Kim, Gabe Schwartz, Michael Zollhoefer, Shunsuke Saito, Stephen Lombardi, Shih-en Wei, Danielle Belko, Shoou-i Yu, Yaser Sheikh, and Jason Saragih. Authentic volumetric avatars from a phone scan. ACM Trans. Graph. , 2022.
- Yoon Ho Cho, Jae Kyeong Kim, and Soung Hie Kim. A personalized recommender system based on web usage mining and decision tree induction. Expert systems with Applications , 23(3):329-342, 2002.
- Jooyoung Choi, Sungwon Kim, Yonghyun Jeong, Youngjune Gwon, and Sungroh Yoon. Ilvr: Conditioning method for denoising diffusion probabilistic models. arXiv preprint arXiv:2108.02938 , 2021.
- Niv Cohen, Rinon Gal, Eli A. Meirom, Gal Chechik, and Yuval Atzmon. 'this is my unicorn, fluffy': Personalizing frozen vision-language representations. In European Conference on Computer Vision (ECCV) , 2022.
- Katherine Crowson. CLIP guided diffusion HQ 256x256. https://colab.research.google.com/ drive/12a_Wrfi2_gwwAuN3VvMTwVMz9TfqctNj , 2021.
- Katherine Crowson, Stella Biderman, Daniel Kornis, Dashiell Stander, Eric Hallahan, Louis Castricato, and Edward Raff. Vqgan-clip: Open domain image generation and editing with natural language guidance. arXiv preprint arXiv:2204.08583 , 2022.
- Jacob Devlin, Ming-Wei Chang, Kenton Lee, and Kristina Toutanova. Bert: Pre-training of deep bidirectional transformers for language understanding. arXiv preprint arXiv:1810.04805 , 2018.
- Prafulla Dhariwal and Alexander Nichol. Diffusion models beat gans on image synthesis. Advances in Neural Information Processing Systems , 34:8780-8794, 2021.
- Yuxuan Ding, Lingqiao Liu, Chunna Tian, Jingyuan Yang, and Haoxuan Ding. Don't stop learning: Towards continual learning for the clip model. arXiv e-prints , pp. arXiv-2207, 2022.
- Tan M Dinh, Anh Tuan Tran, Rang Nguyen, and Binh-Son Hua. Hyperinverter: Improving stylegan inversion via hypernetwork. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pp. 11389-11398, 2022.
- Alireza Fallah, Aryan Mokhtari, and Asuman Ozdaglar. Personalized federated learning: A meta-learning approach. arXiv preprint arXiv:2002.07948 , 2020.
- Rinon Gal, Or Patashnik, Haggai Maron, Gal Chechik, and Daniel Cohen-Or. Stylegan-nada: Clip-guided domain adaptation of image generators. arXiv preprint arXiv:2108.00946 , 2021.
- Peng Gao, Shijie Geng, Renrui Zhang, Teli Ma, Rongyao Fang, Yongfeng Zhang, Hongsheng Li, and Yu Qiao. Clip-adapter: Better vision-language models with feature adapters. arXiv preprint arXiv:2110.04544 , 2021.
- Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, and Yoshua Bengio. Generative adversarial nets. Advances in neural information processing systems , 27, 2014.
- Jinjin Gu, Yujun Shen, and Bolei Zhou. Image processing using multi-code gan prior, 2020.
- Jonathan Ho and Tim Salimans. Classifier-free diffusion guidance. In NeurIPS 2021 Workshop on Deep Generative Models and Downstream Applications , 2021.
- Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising diffusion probabilistic models. Advances in Neural Information Processing Systems , 33:6840-6851, 2020.
- Yihan Jiang, Jakub Koneˇ cn` y, Keith Rush, and Sreeram Kannan. Improving federated learning personalization via model agnostic meta learning. arXiv preprint arXiv:1909.12488 , 2019.
- Gwanghyun Kim, Taesung Kwon, and Jong Chul Ye. Diffusionclip: Text-guided diffusion models for robust image manipulation. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pp. 2426-2435, 2022.
- Ananya Kumar, Aditi Raghunathan, Robbie Jones, Tengyu Ma, and Percy Liang. Fine-tuning can distort pretrained features and underperform out-of-distribution. arXiv preprint arXiv:2202.10054 , 2022.
- Gihyun Kwon and Jong Chul Ye. Clipstyler: Image style transfer with a single text condition. arXiv preprint arXiv:2112.00374 , 2021.
- Adam Letts, Chris Scalf, Alex Spirin, Tom Mason, Chris Allen, Max Ingham, Mike Howles, Nate Baer, and David Sin. Disco diffusion. https://github.com/alembics/disco-diffusion , 2021.
- Dingcheng Li, Zheng Chen, Eunah Cho, Jie Hao, Xiaohu Liu, Xing Fan, Edward Guo, and Yang Liu. Overcoming catastrophic forgetting during domain adaptation of seq2seq language generation. In NAACL 2022 , 2022. URL https://www.amazon.science/publications/ overcoming-catastrophic-forgetting-during-domain-adaptation-of-seq2seq-language-generation .
- Zhi-Song Liu, Li-Wen Wang, Wan-Chi Siu, and Vicky Kalogeiton. Name your style: An arbitrary artist-aware image style transfer. arXiv preprint arXiv:2202.13562 , 2022.
- Yishay Mansour, Mehryar Mohri, Jae Ro, and Ananda Theertha Suresh. Three approaches for personalization with applications to federated learning. arXiv preprint arXiv:2002.10619 , 2020.
- Ana Belen Barragans Martinez, Jose J Pazos Arias, Ana Fernandez Vilas, Jorge Garcia Duque, and Martin Lopez Nores. What's on tv tonight? an efficient and effective personalized recommender system of tv programs. IEEE Transactions on Consumer Electronics , 55(1):286-294, 2009.
- Oscar Michel, Roi Bar-On, Richard Liu, Sagie Benaim, and Rana Hanocka. Text2mesh: Text-driven neural stylization for meshes. arXiv preprint arXiv:2112.03221 , 2021.
- Pamela Mishkin, Lama Ahmad, Miles Brundage, Gretchen Krueger, and Girish Sastry. Dall·e 2 preview risks and limitations. 2022.
- Ryan Murdock. The big sleep, 2021. https://twitter.com/advadnoun/status/ 1351038053033406468 .
- Alex Nichol, Prafulla Dhariwal, Aditya Ramesh, Pranav Shyam, Pamela Mishkin, Bob McGrew, Ilya Sutskever, and Mark Chen. Glide: Towards photorealistic image generation and editing with text-guided diffusion models. arXiv preprint arXiv:2112.10741 , 2021.
- Yotam Nitzan, Kfir Aberman, Qiurui He, Orly Liba, Michal Yarom, Yossi Gandelsman, Inbar Mosseri, Yael Pritch, and Daniel Cohen-Or. Mystyle: A personalized generative prior. arXiv preprint arXiv:2203.17272 , 2022.
- Roni Paiss, Hila Chefer, and Lior Wolf. No token left behind: Explainability-aided image classification and generation. arXiv preprint arXiv:2204.04908 , 2022.
- Or Patashnik, Zongze Wu, Eli Shechtman, Daniel Cohen-Or, and Dani Lischinski. Styleclip: Text-driven manipulation of stylegan imagery. arXiv preprint arXiv:2103.17249 , 2021.
- Mathis Petrovich, Michael J. Black, and G¨ ul Varol. TEMOS: Generating diverse human motions from textual descriptions. In European Conference on Computer Vision (ECCV) , 2022.
- Stanislav Pidhorskyi, Donald A Adjeroh, and Gianfranco Doretto. Adversarial latent autoencoders. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pp. 14104-14113, 2020.
- Alec Radford, Jong Wook Kim, Chris Hallacy, Aditya Ramesh, Gabriel Goh, Sandhini Agarwal, Girish Sastry, Amanda Askell, Pamela Mishkin, Jack Clark, et al. Learning transferable visual models from natural language supervision. arXiv preprint arXiv:2103.00020 , 2021.
- Aditya Ramesh, Mikhail Pavlov, Gabriel Goh, Scott Gray, Chelsea Voss, Alec Radford, Mark Chen, and Ilya Sutskever. Zero-shot text-to-image generation. In International Conference on Machine Learning , pp. 8821-8831. PMLR, 2021.
- Aditya Ramesh, Prafulla Dhariwal, Alex Nichol, Casey Chu, and Mark Chen. Hierarchical text-conditional image generation with clip latents. arXiv preprint arXiv:2204.06125 , 2022.
- Rathvon. Early Reading Assessment: A Practitioner's Handbook . Guilford Publications, 2004. ISBN 9781572309845. URL https://books.google.co.uk/books?id=zX8YzwEACAAJ .
- Elad Richardson, Yuval Alaluf, Or Patashnik, Yotam Nitzan, Yaniv Azar, Stav Shapiro, and Daniel Cohen-Or. Encoding in style: a stylegan encoder for image-to-image translation. arXiv preprint arXiv:2008.00951 , 2020.
- Daniel Roich, Ron Mokady, Amit H Bermano, and Daniel Cohen-Or. Pivotal tuning for latent-based editing of real images. arXiv preprint arXiv:2106.05744 , 2021.
- Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, and Bj¨ orn Ommer. High-resolution image synthesis with latent diffusion models, 2021.
- Chitwan Saharia, William Chan, Saurabh Saxena, Lala Li, Jay Whang, Emily Denton, Seyed Kamyar Seyed Ghasemipour, Burcu Karagol Ayan, S Sara Mahdavi, Rapha Gontijo Lopes, et al. Photorealistic text-toimage diffusion models with deep language understanding. arXiv preprint arXiv:2205.11487 , 2022.
- Christoph Schuhmann, Richard Vencu, Romain Beaumont, Robert Kaczmarczyk, Clayton Mullis, Aarush Katta, Theo Coombes, Jenia Jitsev, and Aran Komatsuzaki. Laion-400m: Open dataset of clip-filtered 400 million image-text pairs. arXiv preprint arXiv:2111.02114 , 2021.
- Aviv Shamsian, Aviv Navon, Ethan Fetaya, and Gal Chechik. Personalized federated learning using hypernetworks. In International Conference on Machine Learning , pp. 9489-9502. PMLR, 2021.
- Gabriel Skantze and Bram Willemsen. Collie: Continual learning of language grounding from languageimage embeddings. Journal of Artificial Intelligence Research , 74:1201-1223, 2022.
- Jiaming Song, Chenlin Meng, and Stefano Ermon. Denoising diffusion implicit models. In International Conference on Learning Representations , 2020.
- Ming Tao, Hao Tang, Songsong Wu, Nicu Sebe, Xiao-Yuan Jing, Fei Wu, and Bingkun Bao. Df-gan: Deep fusion generative adversarial networks for text-to-image synthesis. arXiv preprint arXiv:2008.05865 , 2020.
- Guy Tevet, Brian Gordon, Amir Hertz, Amit H Bermano, and Daniel Cohen-Or. Motionclip: Exposing human motion generation to clip space. arXiv preprint arXiv:2203.08063 , 2022.
- Omer Tov, Yuval Alaluf, Yotam Nitzan, Or Patashnik, and Daniel Cohen-Or. Designing an encoder for stylegan image manipulation. arXiv preprint arXiv:2102.02766 , 2021.
- Maria Tsimpoukelli, Jacob L Menick, Serkan Cabi, SM Eslami, Oriol Vinyals, and Felix Hill. Multimodal few-shot learning with frozen language models. Advances in Neural Information Processing Systems , 34: 200-212, 2021.
- Rotem Tzaban, Ron Mokady, Rinon Gal, Amit H. Bermano, and Daniel Cohen-Or. Stitch it in time: Ganbased facial editing of real videos, 2022.
- Aaron Van Den Oord, Oriol Vinyals, et al. Neural discrete representation learning. Advances in neural information processing systems , 30, 2017.
- Weihao Xia, Yulun Zhang, Yujiu Yang, Jing-Hao Xue, Bolei Zhou, and Ming-Hsuan Yang. Gan inversion: A survey, 2021.
- Tao Xu, Pengchuan Zhang, Qiuyuan Huang, Han Zhang, Zhe Gan, Xiaolei Huang, and Xiaodong He. Attngan: Fine-grained text to image generation with attentional generative adversarial networks. In Proceedings of the IEEE conference on computer vision and pattern recognition , pp. 1316-1324, 2018.
- Paul Yacoubian. Avocado bag, 2022. https://twitter.com/PaulYacoubian/status/ 1542867718071779330 .
- Hui Ye, Xiulong Yang, Martin Takac, Rajshekhar Sunderraman, and Shihao Ji. Improving text-to-image synthesis using contrastive learning. arXiv preprint arXiv:2107.02423 , 2021.
- Jiahui Yu, Yuanzhong Xu, Jing Yu Koh, Thang Luong, Gunjan Baid, Zirui Wang, Vijay Vasudevan, Alexander Ku, Yinfei Yang, Burcu Karagol Ayan, et al. Scaling autoregressive models for content-rich text-to-image generation. arXiv preprint arXiv:2206.10789 , 2022.
- Han Zhang, Jing Yu Koh, Jason Baldridge, Honglak Lee, and Yinfei Yang. Cross-modal contrastive learning for text-to-image generation. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition , pp. 833-842, 2021.
- Kaiyang Zhou, Jingkang Yang, Chen Change Loy, and Ziwei Liu. Learning to prompt for vision-language models. arXiv preprint arXiv:2109.01134 , 2021.
- Jiapeng Zhu, Yujun Shen, Deli Zhao, and Bolei Zhou. In-domain gan inversion for real image editing. arXiv preprint arXiv:2004.00049 , 2020a.
- Jun-Yan Zhu, Philipp Kr¨ ahenb¨ uhl, Eli Shechtman, and Alexei A Efros. Generative visual manipulation on the natural image manifold. In European conference on computer vision , pp. 597-613. Springer, 2016.
- Minfeng Zhu, Pingbo Pan, Wei Chen, and Yi Yang. Dm-gan: Dynamic memory generative adversarial networks for text-to-image synthesis. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition , pp. 5802-5810, 2019.
- Peihao Zhu, Rameen Abdal, Yipeng Qin, and Peter Wonka. Improved stylegan embedding: Where are the good latents?, 2020b.

## GLOSSAR

- **Textual Inversion** — the paper's core process — finding a new pseudo-word embedding in a frozen text-to-image model's embedding space by optimizing a reconstruction objective over a small set of concept images.
- **Pseudo-word (S\*)** — a placeholder string whose embedding vector v* is learned to represent a new, specific concept; treated like any other word in sentences.
- **Personalized text-to-image generation** — the task introduced by the paper — synthesizing novel scenes of user-provided concepts guided by natural language.
- **Distortion–editability tradeoff** — the observed curve in the textual embedding space where embeddings closer to the real word distribution are more easily edited but less faithful, and vice versa; the method's position on it can be shifted via the learning rate.
- **Per-image tokens** — an experimental scheme adding a unique placeholder S_i per training image alongside the universal S*, so shared concept information goes into S* and per-image details into S_i.
- **Extended latent space** — a setup where S* is embedded into multiple learned embeddings (2-word, 3-word), equivalent to describing a concept with multiple pseudo-words.
- **Progressive extension** — a multi-vector setup where additional embedding vectors are introduced after 2,000 and 4,000 training steps.
- **Image Only / Prompt Only** — reference baselines — always outputting training-set images regardless of prompt, versus always following the prompt while ignoring the concept.
- **Bipartite inversion** — a DALL-E 2-inspired approach keeping the DDIM-inverted noise map x_T fixed while changing the conditioning text.
- **Pivotal tuning** — a two-stage approach (from GAN inversion) in which the generator is fine-tuned after pseudo-word optimization to improve reconstruction.
