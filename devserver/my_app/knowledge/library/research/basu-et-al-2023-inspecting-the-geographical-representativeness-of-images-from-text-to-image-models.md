---
id: basu-et-al-2023-inspecting-the-geographical-representativeness-of-images-from-text-to-image-models
titel: Inspecting the Geographical Representativeness of Images from Text-to-Image Models
autor: "Abhipsa Basu, R. Venkatesh Babu, Danish Pruthi"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias, cultural_diversity]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2305.11080"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T10:16:32.604710+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: pdf
---

# Inspecting the Geographical Representativeness of Images from Text-to-Image Models

## PROFIL

Written by Abhipsa Basu, R. Venkatesh Babu and Danish Pruthi (Indian Institute of Science, Bangalore), this scholarly article measures the geographical representativeness of images produced by the text-to-image models DALL·E 2 and Stable Diffusion. Its claim is that, because such models are trained on image-caption pairs mined from an unequally connected internet, their outputs over-represent some nations and under-represent others, with consequences for both representational and allocational harms. The study defines geographical representativeness as the average Likert rating that residents of a country give to model-generated images of common nouns, and pursues four research questions: whether the models are geographically representative; whether naming a country in the prompt improves representativeness; whether realism affects ratings; and whether the evaluation can be automated. It reports a user study with 540 participants from 27 countries recruited via Amazon Mechanical Turk and Prolific, who rated images of ten common nouns (city, beach, house, festival, road, dress, flag, park, wedding, kitchen) generated from country-specific and underspecified prompts. Findings include: average representativeness of 2.39 out of 5 for underspecified prompts, with only the United States and India exceeding 3; a positive correlation with population but none with per-capita GDP; significant gains from country-specific prompts (average rising to 3.49), with DALL·E 2 outperforming Stable Diffusion in that setting; and correlations between realism and representativeness ratings. Two automated approaches — CLIP-based similarity and k-nearest-neighbor estimation — are tested and found inadequate, leading the authors to conclude that user studies remain necessary. The paper situates itself within work on text-to-image generation and societal-bias research in deep learning, citing prior studies of gender and racial bias in DALL·E v1 and stereotypes in Stable Diffusion, and positions geographical representation as an oft-overlooked aspect of inclusive representation. It closes with limitations (coverage of only 27 of 88 targeted countries; only ten nouns) and future directions toward more geographically inclusive models. The article is usable in disciplines and situations of arts education concerned with AI-generated imagery, bias and representation in visual culture, and the critique of generative models' defaults.

## WISSEN

### Purpose and Scope of the Study (pp. 1–2)

This paper by Abhipsa Basu, R. Venkatesh Babu and Danish Pruthi (Indian Institute of Science, Bangalore) measures the **geographical representativeness** of images produced by text-to-image generation models — specifically DALL·E 2 and Stable Diffusion. The authors argue that because such models are trained on image-caption pairs mined from the internet, and internet access is unequally distributed across the world, generated images risk over-representing certain nations while under-representing others. This matters both for representational harms (e.g., a "typical house" looking American rather than Japanese) and allocational harms (biased images used for data augmentation propagate bias further). The study asks how well generated images of common nouns reflect the actual surroundings of people in different countries, whether specifying a country name in the prompt helps, whether realism affects ratings, and whether the evaluation can be automated.

### Approach and Study Design (pp. 2–4)

The authors define **geographical representativeness (GR)** as the average rating (on a 1–5 Likert scale) that participants from a country give to model-generated images of common nouns, and **realism (R)** as the average realism rating. Four research questions guide the work:

1. RQ1: Are images from DALL·E 2 and Stable Diffusion geographically representative? Do they over-represent rich or populous nations?
2. RQ2: To what extent does specifying the country name in the input improve representativeness?
3. RQ3: Does the realism of images impact participants' ratings about geographical representativeness?
4. RQ4: How feasible is it to automatically assess the geographical representativeness of generated images?

The study reached out to residents of 88 countries via Amazon Mechanical Turk and Prolific, obtaining sufficient responses from 27 countries (selected through population-weighted random sampling): the USA, Canada, Mexico, Brazil, Chile, the UK, Italy, Spain, Greece, Japan, Korea, India, Israel, Australia, South Africa, Belgium, Poland, Portugal, Germany, France, Latvia, Hungary, the Czech Republic, Estonia, New Zealand, Finland, and Slovenia.

Ten common nouns were chosen by extracting the most frequent nouns from the Conceptual Captions dataset using an NLTK POS-tagger, excluding universal nouns like sky and sun: **city, beach, house, festival, road, dress, flag, park, wedding, and kitchen**. Two prompt types were used: country-specific ("high definition image of a typical [artifact] in [country]") and underspecified ("high definition image of a [artifact]").

Each of the 540 participants evaluated 80 images (4 per noun per model, from both DALL·E 2 and Stable Diffusion), rating how well each image reflects the artifact in their surroundings. Participants also rated photo-realism and self-assessed how realism influenced their scores. Responses were validated with four trick questions (e.g., showing mangoes when asked about apples), and participants' residence was re-confirmed. Inter-rater agreement was high: in 19 of 27 countries, over 50% of participants chose the most common option (highest agreement for flags at 81%, lowest for kitchens at 41%).

### Results: Geographical Representativeness (pp. 4–6)

**RQ1 (pp. 4–5).** For underspecified prompts, 25 of 27 countries scored below 3 out of 5. Only the United States (3.35) and India (3.23) exceeded 3; Canada followed at 2.82. The lowest scores came from Greece (1.94), Japan (1.95) and Finland (2.03). The average across all countries was 2.39. Regarding wealth and population:

1. No correlation was found between GR scores and per-capita GDP (Pearson ρ = -0.03), and no statistically significant difference between "Rich West" countries and others.
2. GR scores were positively correlated with population (ρ = 0.64), suggesting training datasets contain many images from populous countries.

**RQ2 (pp. 4–5).** Including the country name in the prompt significantly increased GR scores (paired t-test, p < 0.05): by 1.44 points on average for DALL·E 2 and 0.75 for Stable Diffusion. The overall average rose from 2.39 to 3.49. However, 14 of 27 countries still scored only between 3 and 3.5, indicating considerable headroom for improvement.

**RQ3 (p. 5).** Realism and geographical representativeness scores were correlated: for Stable Diffusion, Pearson correlation of 0.62 (unspecified) and 0.47 (country-specified); for DALL·E 2, 0.21 and 0.57 respectively. Participants self-assessed realism's influence at an average of 3.5 on a 1–5 scale. Interestingly, average realism scores were significantly *lower* when prompts excluded the country name (p < 0.05), though some countries (e.g., the US and Brazil) showed the opposite trend.

**Model comparison (p. 6).** For country-specific prompts, DALL·E 2 outperformed Stable Diffusion by about 0.6 points (statistically significant); for country-agnostic prompts, no statistically significant difference was found.

### Feasibility of Automating the Evaluation (pp. 6–8)

The authors test two automated approaches for RQ4:

1. **CLIP-based similarity (pp. 6–8).** CLIP similarity scores correctly reproduced high-level findings — images generated with country-specific prompts scored higher (p < 0.001), with 98.7% agreement for DALL·E 2 and 96.4% for Stable Diffusion in cases where country-specified images scored higher. However, CLIP contradicted finer-grained human findings: it found no significant difference between the two models with country names (humans preferred DALL·E 2), and preferred Stable Diffusion without country names (humans found no difference). Correlation between country-wise human GR scores and CLIP scores was essentially nil for country-specified images (ρ = 0.01) and weak for unspecified ones (ρ = 0.34). On a benchmark of image pairs, CLIP matched human preferences only 52.4% of the time (random chance: 50%).
2. **k-nearest neighbor estimation (p. 8).** Using DALL·E 2 ratings as training data and Stable Diffusion ratings for testing, with image features from CLIP's vision model (k = 1, since only 4 annotated images per noun-country pair exist), the correlation between estimated and human scores was moderate for unspecified prompts (ρ = 0.46) but absent for country-specific prompts (ρ = 0.01). Mean squared errors were 1.39 (unspecified) and 1.56 (country-specified) — both *worse* than a naive baseline predicting 3.0 for every image (MSE 1.18 and 0.83). Alternative feature extractors (VGG16, ResNet18, ResNet50, ViT, CLIPVision) all performed worse than the baseline.

The authors conclude that both approaches are inadequate, and that automatically estimating geographical representativeness is fundamentally challenging — user studies remain necessary.

### Limitations and Future Directions (p. 9)

Key limitations include: sufficient responses from only 27 of 88 targeted countries (with fewer than 5 responses from Nepal, Bangladesh, Malaysia, Turkey, Singapore, Argentina, Kenya, Venezuela, Pakistan, Indonesia, Nigeria, Romania, Colombia, Namibia, and zero from many others), reflecting unequal internet access and the skew of crowdsourcing platforms; and evaluation of only 10 nouns (adding more would lengthen surveys and reduce participation). Future directions include aggregating images to scale evaluation, better documenting training-data sources, collecting more data from under-represented countries, and improving participation from marginalized nations in model development and evaluation.

### Related Work and Conclusion (pp. 9–10)

The paper situates itself within work on text-to-image generation (GANs, autoregressive transformers, diffusion models) and societal-bias research in deep learning (image classification, captioning, face recognition, image search, art creation), noting prior studies of gender and racial bias in DALL·E v1 and stereotypes in Stable Diffusion. The authors position geographical representation as an oft-overlooked aspect of inclusive representation. They conclude that current text-to-image models generate images that poorly reflect most of the world's surroundings unless explicitly prompted with country names, and even then scores remain modest, underscoring the need for more geographically inclusive models.

### Figures (p. 1–15)

*Fig. 1 (p. 1):* An illustrative question from our study, where a participant (in this case, from the United States) is presented with an image of a common noun (a house), generated from the Stable Diffusion model. The participant is asked to rate the generated image on how well it reflects the houses in their surroundings. — The picture shows a photograph of a two-story suburban house at dusk, with a dark gabled roof, a columned front porch with a warmly lit door, symmetrically arranged windows glowing with light, trees and shrubs in the front yard, and a sidewalk and street in the foreground under a partly cloudy sky. Below the photograph is a horizontal rating scale made up of five empty radio-button circles numbered 1 through 5. Beneath 1 is the red label "Not at all", and beneath 5 is the green label "To a great extent". _(Lettering in the image, read by the image model, not confirmed: "Not at all", "To a great extent")_

*Fig. 2 (p. 3):* Agreement among participants. We plot the percentage of participants from each country that choose the most common option (for that country). We see that there is a considerable agreement among respondents, as about half the participants in many countries agree on one out of five options. — This is a horizontal bar chart. Along the vertical axis are 27 country names, each paired with a gray horizontal bar and a numeric percentage, while the horizontal axis is labeled “Percentage of users that pick the most common option” and is marked at 0, 15, 30, 45, and 60. The highest value shown is Latvia at 55.6 and the lowest is the United States at 38.3. _(Lettering in the image, read by the image model, not confirmed: “Percentage of users that pick the most common option”)_

*Fig. 3 (p. 6):* Qualitative examples of images of four common nouns generated by DALL·E 2 and Stable Diffusion models. Through these examples and others, we see that the default generations often reflect artifacts from US and Canada. For example, the average score (in unspecified case) for the images of houses generated through DALL·E 2 is 3 . 95 for US and Canada, and 2 . 09 for the remaining countries. — The picture is a table of photographs organized into four rows and six columns. The rows are labeled "House," "Flag," "City," and "Wedding," and the columns are labeled "Unspecified (default)," "Brazil," "Mexico," "Italy," "S. Korea," and "Japan." The "Unspecified (default)" column contains two photographs per row, while each of the other columns contains one photograph per row, all showing the subject indicated by the row label. _(Lettering in the image, read by the image model, not confirmed: "House,", "Flag,", "City,", "Wedding,", "Unspecified (default),", "Mexico,", "Italy,", "S. Korea,", "Japan.", "Unspecified (default)")_

*Fig. 4 (p. 6):* DALL-E 2 vs Stable Diffusion: Average geographical representativeness scores for images generated by DALL·E 2 and Stable Diffusion, with and without country-specific prompts. — This is a horizontal bar chart with four bars, each showing a horizontal error bar, plotted against a horizontal axis labeled "Average geographical representativeness (averaged over all countries)" with a scale from 0 to 5. The legend identifies the bars as "DALL-E 2 unspecified (default)" in light green, "DALL-E 2 with country name" in dark green, "Stable Diffusion unspecified (default)" in light gray, and "Stable Diffusion score with country name" in dark gray. The dark green bar extends furthest to the right near 4, the dark gray bar reaches just past 3, and the light gray and light green bars both reach just past 2. _(Lettering in the image, read by the image model, not confirmed: "Average geographical representativeness (averaged over all countries)", "DALL-E 2 unspecified (default)", "DALL-E 2 with country name", "Stable Diffusion unspecified (default)", "Stable Diffusion score with country name")_

*Fig. 5 (p. 9):* The number of participants available for research studies on Prolific are heavily skewed, and have few (or no) participants from many poor and developing nations. Such disparity is a serious challenge for inclusive model development and evaluation. — This is a horizontal bar chart. The vertical axis lists “Total,” “UK + USA,” and country names from “South Africa” down to “Luxembourg,” while the horizontal axis is labeled “Number of Participants” with a logarithmic scale marked “10,” “10000,” and “1000000.” Each bar ends in a numeric label, with “Total” at “1,21,416,” “UK + USA” at “81,000,” “South Africa” at “7,746,” and the shortest bar, “Luxembourg,” at “26.” _(Lettering in the image, read by the image model, not confirmed: “Total,”, “UK + USA,”, “South Africa”, “Luxembourg,”, “10000,”, “1000000.”, “Total”, “1,21,416,”, “UK + USA”, “81,000,”, “South Africa”, “7,746,”, “Luxembourg,”)_

*Fig. 6 (p. 12):* Qualitative examples of images of five common nouns (City, Beach, House, Festival and Road) generated by DALL·E 2 , for the default (unspecified) and the country specific prompts. From the shown examples, we note that the default generations often reflect artifacts from the US, whereas the representativeness is lower for Japan and Chile. The trend remains similar even after specifying the country name in the prompts, though the GR scores increase for all countries. (SA: South Africa, Aus: Australia) — This is a table of color photographs arranged in five columns labeled “City,” “Beach,” “House,” “Festival,” and “Road,” and seven rows labeled “Unspecified,” “US,” “Chile,” “UK,” “Japan,” “SA,” and “Aus.” Each cell contains one photograph matching its column category, with the row label at the left and the column label at the top. The photographs show cityscapes, beaches, houses, festival scenes, and roads.

*Fig. 7 (p. 13):* Qualitative examples of images of the five other common nouns (Dress, Flag, Park, Wedding and Kitchen) generated by DALL·E 2 for the default (unspecified) and the country specific prompts. From the shown examples, we note that the default generations often reflect artifacts from the US, whereas the representativeness is lower for Japan and Chile. The trend remains similar even after specifying the country name in the prompts, though the GR scores increase for all countries. (SA: South Africa, Aus: Australia) — The picture is a table of photographs arranged in a grid, with column headers “Dress,” “Flag,” “Park,” “Kitchen,” and “Wedding,” and row labels “Unspecified,” “US,” “Chile,” “UK,” “Japan,” “SA,” and “Aus.” Each cell contains one photo showing, respectively, a dress, a flag, a park or grassy area, a kitchen interior, or a wedding scene. The “Unspecified” row shows a plain light dress, a red-and-white flag, a paved park path, a white kitchen, and a couple in wedding clothing, while the country rows show different versions of those same five categories.

*Fig. 8 (p. 14):* Qualitative examples of images of the five other common nouns (City, Beach, House, Festival, Road) generated by Stable Diffusion, for the default (unspecified) and the country specific prompts. Like the DALL·E 2 generated images, we note that the default generations often reflect artifacts from the US, whereas the representativeness is lower for Japan and Chile. The trend remains similar even after specifying the country name in the prompts, though the GR scores increase for all countries. (SA: South Africa, Aus: Australia) — The picture is a table with seven rows and five columns of color photographs. The column headers read “City”, “Beach”, “House”, “Festival”, and “Road”, and the row labels read “Unspecified”, “US”, “Chile”, “UK”, “Japan”, “SA”, and “Aus”. Each cell contains one photograph matching its row and column, showing scenes such as city skylines, beaches, houses, festival crowds, and roads.

*Fig. 9 (p. 15):* Qualitative examples of images of the five other common nouns (Dress, Flag, Park, Kitchen, Wedding) generated by Stable Diffusion, for the default (unspecified) and the country specific prompts. Once again, we note that the default generations often reflect artifacts from the US, whereas the representativeness is lower for Japan and Chile. The trend remains similar even after specifying the country name in the prompts, though the GR scores increase for all countries. (SA: South Africa, Aus: Australia) — The image is a table-like grid of color photographs arranged in seven rows and five columns. The column headers read “Dress,” “Flag,” “Park,” “Kitchen,” and “Wedding,” and the row labels read “Unspecified,” “US,” “Chile,” “UK,” “Japan,” “SA,” and “Aus.” Each cell contains one photograph matching its column category, such as garments, flags, parks, kitchens, or wedding scenes, with varying styles and settings across the rows.

<!-- quelle: Inspecting the Geographical Representativeness of Images from Text-to-Image Models (p. 1–15) -->

## LITERATUR

<!-- quelle: References (p. 10–11) -->

- Dall·e 2: Extending creativity, Jul 2022. 1
- The World Bank. Indiviuals using the internet. 2018. 1, 9
- Hritik Bansal, Da Yin, Masoud Monajatipoor, and Kai-Wei Chang. How well can text-to-image generative models understand ethical natural language interventions? arXiv preprint arXiv:2210.15230 , 2022. 7
- Federico Bianchi, Pratyusha Kalluri, Esin Durmus, Faisal Ladhak, Myra Cheng, Debora Nozza, Tatsunori Hashimoto, Dan Jurafsky, James Zou, and Aylin Caliskan. Easily accessible text-to-image generation amplifies demographic stereo-
- types at large scale. arXiv preprint arXiv:2211.03759 , 2022. 2, 9, 10
- Joy Buolamwini and Timnit Gebru. Gender shades: Intersectional accuracy disparities in commercial gender classification. In Conference on fairness, accountability and transparency , pages 77-91. PMLR, 2018. 9
- Pew Research Center. Internet/broadband fact sheet. 2021. 1, 9
- Jaemin Cho, Jiasen Lu, Dustin Schwenk, Hannaneh Hajishirzi, and Aniruddha Kembhavi. X-lxmert: Paint, caption and answer questions with multi-modal transformers. arXiv preprint arXiv:2009.11278 , 2020. 9
- Jaemin Cho, Abhay Zala, and Mohit Bansal. Dalleval: Probing the reasoning skills and social biases of text-to-image generative transformers. arXiv preprint arXiv:2202.04053 , 2022. 2, 7, 10
- Jean-R´ emy Conti, Nathan Noiry, Stephan Clemencon, Vincent Despiegel, and St´ ephane Gentric. Mitigating gender bias in face recognition using the von mises-fisher mixture model. In International Conference on Machine Learning , pages 4344-4369. PMLR, 2022. 9
- Alexey Dosovitskiy, Lucas Beyer, et al. An image is worth 16x16 words: Transformers for image recognition at scale. arXiv preprint arXiv:2010.11929 , 2020. 8
- Shuyang Gu, Dong Chen, et al. Vector quantized diffusion model for text-to-image synthesis. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pages 10696-10706, 2022. 9
- Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. Deep residual learning for image recognition. In Proceedings of the IEEE conference on computer vision and pattern recognition , pages 770-778, 2016. 8
- Lisa Anne Hendricks, Kaylee Burns, Kate Saenko, Trevor Darrell, and Anna Rohrbach. Women also snowboard: Overcoming bias in captioning models. In Proceedings of the European Conference on Computer Vision (ECCV) , pages 771787, 2018. 2, 9
- Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising diffusion probabilistic models. Advances in Neural Information Processing Systems , 33:6840-6851, 2020. 1
- Ben Hutchinson, Jason Baldridge, and Vinodkumar Prabhakaran. Underspecification in scene description-todepiction tasks. arXiv preprint arXiv:2210.05815 , 2022. 2
- Xiujun Li, Xi Yin, Chunyuan Li, Pengchuan Zhang, Xiaowei Hu, Lei Zhang, Lijuan Wang, Houdong Hu, Li Dong, Furu Wei, et al. Oscar: Object-semantics aligned pre-training for vision-language tasks. In European Conference on Computer Vision , pages 121-137. Springer, 2020. 3
- Jiasen Lu, Dhruv Batra, Devi Parikh, and Stefan Lee. Vilbert: Pretraining task-agnostic visiolinguistic representations for vision-and-language tasks. Advances in neural information processing systems , 32, 2019. 3
- Elman Mansimov, Emilio Parisotto, Jimmy Lei Ba, and Ruslan Salakhutdinov. Generating images from captions with attention. arXiv preprint arXiv:1511.02793 , 2015. 9
- Dana¨ e Metaxa, Michelle A Gan, Su Goh, Jeff Hancock, and James A Landay. An image of society: Gender and racial
- representation and impact in image search results for occupations. Proceedings of the ACM on Human-Computer Interaction , 5(CSCW1):1-23, 2021. 9
- Alex Nichol, Prafulla Dhariwal, et al. Glide: Towards photorealistic image generation and editing with text-guided diffusion models. arXiv preprint arXiv:2112.10741 , 2021. 9
- Alec Radford, Jong Wook Kim, et al. Learning transferable visual models from natural language supervision. In ICML , pages 8748-8763. PMLR, 2021. 2, 7, 8
- Vikram V Ramaswamy, Sunnie SY Kim, and Olga Russakovsky. Fair attribute classification through latent space de-biasing. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition , pages 9301-9310, 2021. 9
- Vikram V Ramaswamy, Sing Yu Lin, et al. Beyond webscraping: Crowd-sourcing a geographically diverse image dataset. arXiv preprint arXiv:2301.02560 , 2023. 9
- Aditya Ramesh, Prafulla Dhariwal, Alex Nichol, Casey Chu, and Mark Chen. Hierarchical text-conditional image generation with clip latents. arXiv preprint arXiv:2204.06125 , 2022. 1, 2, 5, 9
- Aditya Ramesh, Mikhail Pavlov, et al. Zero-shot text-toimage generation. In ICML , pages 8821-8831. PMLR, 2021. 3, 9
- Scott Reed, Zeynep Akata, Xinchen Yan, Lajanugen Logeswaran, Bernt Schiele, and Honglak Lee. Generative adversarial text to image synthesis. In International conference on machine learning , pages 1060-1069. PMLR, 2016. 9
- Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, and Bj¨ orn Ommer. High-resolution image synthesis with latent diffusion models, 2021. 1, 2, 5, 9
- Candace Ross, Boris Katz, and Andrei Barbu. Measuring social biases in grounded vision and language embeddings. arXiv preprint arXiv:2002.08911 , 2020. 2
- Nataniel Ruiz, Yuanzhen Li, Varun Jampani, Yael Pritch, Michael Rubinstein, and Kfir Aberman. Dreambooth: Fine tuning text-to-image diffusion models for subject-driven generation. arXiv preprint arXiv:2208.12242 , 2022. 1, 9
- Chitwan Saharia, William Chan, et al. Photorealistic text-toimage diffusion models with deep language understanding. arXiv preprint arXiv:2205.11487 , 2022. 9
- Michael Saxon and William Yang Wang. Multilingual conceptual coverage in text-to-image models. 7
- Piyush Sharma, Nan Ding, Sebastian Goodman, and Radu Soricut. Conceptual captions: A cleaned, hypernymed, image alt-text dataset for automatic image captioning. In Proceedings of ACL , 2018. 3
- Emily Sheng, Kai-Wei Chang, Premkumar Natarajan, and Nanyun Peng. The woman worked as a babysitter: On biases in language generation. arXiv preprint arXiv:1909.01326 , 2019. 9
- Emily Sheng, Kai-Wei Chang, Premkumar Natarajan, and Nanyun Peng. Societal biases in language generation: Progress and challenges. arXiv preprint arXiv:2105.04054 , 2021. 9
- Karen Simonyan and Andrew Zisserman. Very deep convolutional networks for large-scale image recognition. arXiv preprint arXiv:1409.1556 , 2014. 8
- Ramya Srinivasan and Kanji Uchino. Biases in generative art: A causal look from the lens of art history. In Proceedings of the 2021 ACM Conference on Fairness, Accountability, and Transparency , pages 41-51, 2021. 9
- Ryan Steed and Aylin Caliskan. Image representations learned with unsupervised pre-training contain human-like biases. In Proceedings of the 2021 ACM conference on fairness, accountability, and transparency , pages 701-713, 2021. 2
- Lukas Struppek, Dominik Hintersdorf, and Kristian Kersting. The biased artist: Exploiting cultural biases via homoglyphs in text-guided image generation models. arXiv preprint arXiv:2209.08891 , 2022. 7
- Weijie Su, Xizhou Zhu, et al. Vl-bert: Pre-training of generic visual-linguistic representations. arXiv preprint arXiv:1908.08530 , 2019. 3
- Ming Tao, Hao Tang, et al. Df-gan: Deep fusion generative adversarial networks for text-to-image synthesis. arXiv preprint arXiv:2008.05865 , 2020. 9
- Schrasing Tong and Lalana Kagal. Investigating bias in image classification using model explanations. arXiv preprint arXiv:2012.05463 , 2020. 9
- Ashish Vaswani, Noam Shazeer, et al. Attention is all you need. Advances in neural information processing systems , 30, 2017. 1, 9
- Robert Wolfe and Aylin Caliskan. Markedness in visual semantic ai. arXiv preprint arXiv:2205.11378 , 2022. 2
- Jiahui Yu, Yuanzhong Xu, et al. Scaling autoregressive models for content-rich text-to-image generation. arXiv preprint arXiv:2206.10789 , 2022. 1, 9
- Han Zhang, Tao Xu, Hongsheng Li, Shaoting Zhang, Xiaogang Wang, Xiaolei Huang, and Dimitris N Metaxas. Stackgan: Text to photo-realistic image synthesis with stacked generative adversarial networks. In Proceedings of the IEEE international conference on computer vision , pages 59075915, 2017. 9
- Yi Zhang and Jitao Sang. Towards accuracy-fairness paradox: Adversarial example-based data augmentation for visual debiasing. In Proceedings of the 28th ACM International Conference on Multimedia , MM '20, page 4346-4354, New York, NY, USA, 2020. Association for Computing Machinery. 9
- Dora Zhao, Angelina Wang, and Olga Russakovsky. Understanding and evaluating racial biases in image captioning. In Proceedings of the IEEE/CVF International Conference on Computer Vision , pages 14830-14840, 2021. 9
- Minfeng Zhu, Pingbo Pan, Wei Chen, and Yi Yang. Dm-gan: Dynamic memory generative adversarial networks for textto-image synthesis. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition , pages 5802-5810, 2019. 9

## GLOSSAR

- **Geographical representativeness (GR)** — the average rating (1–5) that participants from a given country assign to model-generated images of common nouns, indicating how well the images reflect their physical surroundings.
- **Realism (R)** — the average photo-realism rating (1–5) given by participants from a country to images generated by a model using a given prompt.
- **Underspecified (unspecified) prompt** — an input query of the form "high definition image of a [artifact]" that omits any country name, used to assess a model's default generations.
- **Country-specific prompt** — an input query of the form "high definition image of a typical [artifact] in [country]", designed to elicit the most common form of a concept in the named country.
- **Rich West countries** — a grouping of nations used in the analysis, defined per worldpopulationreview.com's listing of Western countries.
- **Trick questions** — four validation questions embedded in the survey (e.g., showing mangoes when asking about apples) used to discard inattentive participants.
