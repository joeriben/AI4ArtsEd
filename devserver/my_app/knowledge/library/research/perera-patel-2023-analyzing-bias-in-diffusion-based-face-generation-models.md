---
id: perera-patel-2023-analyzing-bias-in-diffusion-based-face-generation-models
titel: Analyzing Bias in Diffusion-based Face Generation Models
autor: "Malsha V. Perera, Vishal M. Patel"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2305.06402"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:43:13.400694+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: pdf
---

# Analyzing Bias in Diffusion-based Face Generation Models

## PROFIL

This scholarly article by Malsha V. Perera and Vishal M. Patel (Johns Hopkins University) investigates bias in diffusion-based face generation models with respect to perceived gender, race, and age, and argues that diffusion models amplify distribution bias present in the training data, that this bias depends heavily on training dataset size, and that GAN-based models trained on balanced datasets with larger sample counts show less bias and better preserve the attribute composition of the training data. The authors deliberately measure perceived rather than objective attributes, holding that gender and race are shaped by complex social factors, and are further motivated by prior evidence (Somepalli et al.) that diffusion models memorize and replicate training data, especially with small training sets. A related-work section situates the study in research on generative models (GANs, DDPMs), bias in computer vision and in GANs (Jain et al., Maluleke et al., mitigation approaches by Yu et al., Tan et al., Kenfack et al.), bias in text-to-image diffusion systems (Luccioni et al., Naik et al.), and data replication (Feng et al., Carlini et al.), noting that no prior work has studied bias in diffusion-based face generation while varying training dataset size. The method trains a lighter version of ADM for unconditional diffusion-based face generation and StyleGAN2-ADA for comparison, on FFHQ (70,000 images, used for gender and age analysis) and FairFace-BW (28,760 images restricted to the Black and White categories, used for race and gender analysis), with ResNet-18-based attribute classifiers determining perceived attribute distributions. Experiments on balanced subsets of 300 to 10,000 samples per attribute, each generation repeated five times, show that diffusion models skew outputs (e.g., toward the White class on FairFace-BW, with extreme bias at 5000 and 10,000 samples, and toward younger faces on FFHQ), while GAN models match balanced gender distributions for subsets larger than 1000 samples and consistently preserve balanced racial distributions regardless of size. FID scores are reported per attribute class, with diffusion quality following a pattern of starting low, increasing, then decreasing with dataset size, which the authors attribute to data replication at small sizes. The discussion attributes diffusion bias partly to replication that skews rather than reproduces the training attribute distribution, acknowledges possible classifier bias while reporting over 95% accuracy, cautions researchers using diffusion-based face generation in downstream tasks requiring balanced models, and calls for bias mitigation techniques, with future work proposed on Latent Diffusion Models, attributes such as hair and makeup, and Variational Autoencoders. The article is usable in computer vision, machine learning, and media-arts education contexts addressing generative image synthesis, dataset construction, and representation bias in AI-generated imagery.

## WISSEN

### Purpose and Thesis (pp. 1–2)

This paper by Malsha V. Perera and Vishal M. Patel (Johns Hopkins University) investigates bias in diffusion-based face generation models with respect to perceived gender, race, and age. The authors' central claims are: (1) diffusion models amplify distribution bias present in the training data; (2) this bias is heavily influenced by the size of the training dataset; and (3) GAN-based models trained on balanced datasets with larger sample counts show less bias and better preserve the attribute composition of the training data. The authors deliberately measure *perceived* attributes rather than objective ones, arguing that gender and race are shaped by complex social factors, not physical characteristics alone. A further motivation is prior evidence (Somepalli et al.) that diffusion models memorize and replicate training data, especially with small training sets, raising the question of whether sample count affects bias.

### Related Work (pp. 2–3)

The paper situates itself in several research strands:

- **Generative models**: GANs (generator vs. discriminator in a minimax objective) and Denoising Diffusion Probabilistic Models (DDPMs), which use a T-step Markovian forward process (adding Gaussian noise) and a reverse denoising process.
- **Bias in computer vision**: studies showing face recognition algorithms are biased toward gender and race (e.g., Albeiro et al. on gender distribution; Krishnapriya et al. on race and skin tone; work on skin brightness, hairstyles, makeup). Mitigation efforts include Wang et al.'s framework for measuring and mitigating intrinsic bias and Dhar et al.'s distillation-based approach.
- **Bias in GANs**: Jain et al. found GAN face models amplify gender and skin-tone bias on unbalanced data; Maluleke et al. found GANs preserve the racial composition of training data. Mitigation methods include Inclusive GAN (Yu et al., improving data coverage), Tan et al.'s latent-space retraining, and Kenfack et al.'s gradient-clipping strategy.
- **Bias in diffusion models**: Luccioni et al. and Naik et al. found text-to-image systems over-represent whiteness and masculinity and show bias across gender, age, race, and geography. The authors state no prior work has studied bias in diffusion-based face generation while varying training dataset size.
- **Data replication**: Feng et al. (GANs replicate training data, decreasing with dataset complexity/size), Somepalli et al. (diffusion content replication), and Carlini et al. (diffusion models memorize data and leak more training data than GANs).

### Method: Datasets and Models (p. 3)

The study uses two datasets:

- **FFHQ** (Flickr Faces HQ): 70,000 aligned 1024×1024 images from Flickr; 55.3% female, 44.7% male; age distribution 14.5% (0-10), 11% (11-20), 29% (21-30), 22.2% (31-40), 12.6% (41-50), 7.2% (51-60), 3.4% (above 60). Used for gender and age analysis.
- **FairFace-BW**: a subset of the FairFace dataset (108,501 images of non-public figures across seven racial groups and two genders), restricted to the 'Black' and 'White' categories: 28,760 images, 57.47% White, 42.53% Black, 51.4% male, 48.6% female. Used for race and gender analysis.

Models: a lighter version of ADM for unconditional diffusion-based face generation, and StyleGAN2-ADA for the GAN comparison. Attribute classifiers (ResNet-18 based) fine-tuned on these datasets determine the perceived attribute distributions.

### Experiments and Results (pp. 3–7)

**Attribute distribution of diffusion generations (pp. 3–4)**: A diffusion model trained on the complete FFHQ dataset generated 58% female / 42% male samples (vs. 55.3%/44.7% in training). The generated samples were distributed across the age ranges as follows: 14.5% in 0-10, 11% in 11-20, 29% in 21-30, 22.2% in 31-40, 12.6% in 41-50, 7.2% in 51-60, and 3.4% above 60 — the same percentages as the training data, though the discussion notes the proportion of faces in age groups above 50 decreased compared to the training distribution. On FairFace-BW, the diffusion model generated 66% White / 34% Black (vs. 57.47%/42.53%) and 54% male / 46% female.

**Effect of dataset size (pp. 4–7)**: Models were trained on balanced subsets of 300, 700, 1000, 5000, and 10000 samples per attribute, with generation repeated five times to obtain mean distributions. Findings:

- On FFHQ gender subsets (50/50 balanced), diffusion models showed the highest gender bias at sizes 300 and 10000 (predominantly female outputs); 700 and 5000 produced distributions closer to training; 1000 generated more males than females.
- On FairFace-BW gender subsets, diffusion outputs were biased toward females, with bias amplified as subset size increased.
- GAN models matched the balanced gender distribution for subsets larger than 1000 samples; at 300 and 700 they showed pronounced bias (toward males on FFHQ, toward females on FairFace-BW).
- On race (FairFace-BW, 50/50 balanced), diffusion models showed strong bias toward the White class, with extreme bias at 5000 and 10000 samples; GAN models consistently preserved the balanced racial distribution regardless of size, consistent with Maluleke et al.
- On age (FFHQ, each of seven age ranges roughly 14.3% of the subset), diffusion models showed no consistent pattern across sizes; GAN models generally aligned with training except for under-generating the 11-20 and above-60 groups.

**Perceptual quality (FID) (pp. 4, 7–8)**: FID scores (lower = higher quality) were reported per attribute class. Diffusion models showed class-dependent quality (e.g., White images higher quality except at 10000 samples; age groups above 21 generally better than under 20). GAN FID scores decreased gradually as dataset size increased (e.g., FFHQ-10000 gender: 17.85 male / 18.68 female). Diffusion FID scores followed a pattern of starting low, increasing, then decreasing with dataset size—the low scores at smallest sizes likely reflecting data replication making generated and training distributions more similar.

**Attribute classifiers (pp. 4–5)**: FFHQ-based classifiers achieved 99.9% (gender) and 95% (age) accuracy, trained on 69,700 images with 300 held out for testing; FairFace-based classifiers achieved 99.15% (gender) and 97.0% (race).

### Discussion (pp. 5–8)

The direction of gender bias depends on the training dataset (female bias on FFHQ, male bias on FairFace-BW). Diffusion models trained on FFHQ are biased toward younger faces; on FairFace-BW they perpetuate bias toward the White class. The authors attribute diffusion bias partly to data replication: certain samples are replicated more frequently, biasing the output distribution, and replication is more common with smaller training sets (consistent with Feng et al. and Somepalli et al.). Replication in diffusion models does not reproduce the training attribute distribution but skews it. GANs replicate less. The authors acknowledge their automated classifiers could carry bias but report over 95% accuracy and no category bias (confusion matrices in supplementary materials). They caution researchers using diffusion-based face generation in downstream tasks requiring balanced models, note that dataset size and complexity (including lighting, hair, makeup) matter, and call for bias mitigation techniques. Future work: Latent Diffusion Models, attributes such as hair and makeup, and Variational Autoencoders.

### Conclusion (pp. 8–9)

The study's three main results: (1) diffusion models exacerbate distribution bias in training data across attributes and datasets; (2) bias in diffusion models' attribute distribution depends heavily on dataset size; (3) GAN-based models trained with larger samples of balanced datasets exhibit less bias across attributes.

### Figures (p. 3–7)

*Image 1 (p. 3):* — The image shows two pie charts positioned side by side. The left chart is labeled "FFHQ - Train" and contains an orange section marked "44.7%" and a yellow section marked "55.3%". The right chart is labeled "FFHQ - Generated" and contains an orange section marked "42.3%" and a yellow section marked "57.7%". To the left of the charts, a legend titled "Gender" indicates that orange represents "Male" and yellow represents "Female". _(Lettering in the image, read by the image model, not confirmed: "FFHQ - Train", "FFHQ - Generated", "42.3%", "57.7%")_

*Image 2 (p. 3):* — The image shows two pie charts positioned side by side. The chart on the left is labeled "FFHQ - Train" and the chart on the right is labeled "FFHQ - Generated". A legend on the left is titled "Age" and lists the categories "0-10", "11-20", "21-30", "31-40", "41-50", and "51-60", with an additional entry at the bottom that is not fully legible. The left pie chart displays percentage labels 29.0%, 22.2%, 12.5%, 7.3%, 3.4%, 14.5%, and 11.0%, while the right pie chart displays 31.7%, 18.5%, 12.7%, 6.9%, 2.8%, 15.8%, and 11.6%. _(Lettering in the image, read by the image model, not confirmed: "FFHQ - Train", "FFHQ - Generated")_

*Fig. 3 (p. 4):* Gender distribution in the FairFace-BW training data (left) and generated data (right) using diffusion model. — The image contains two pie charts displayed side by side. The left chart is titled "FairFace-BW - Train" and shows an orange segment labeled "51.4%" and a yellow segment labeled "48.6%." The right chart is titled "FairFace-BW - Generated" and shows an orange segment labeled "54.2%" and a yellow segment labeled "45.8%." A legend on the left side indicates that orange corresponds to "Male" and yellow corresponds to "Female" under the category "Gender." _(Lettering in the image, read by the image model, not confirmed: "51.4%", "48.6%.", "FairFace-BW - Generated", "54.2%", "45.8%.")_

*Fig. 4 (p. 4):* Racial distribution in FairFace-BW training data (left) and generated data (right) using diffusion model. — The image shows two side-by-side pie charts. The left chart is titled "FairFace-BW - Train" and is divided into an orange segment labeled "57.5%" and a yellow segment labeled "42.5%". The right chart is titled "FairFace-BW - Generated" and is divided into an orange segment labeled "65.7%" and a yellow segment labeled "34.3%". A legend at the left, under the heading "Race", identifies the orange color as "White" and the yellow color as "Black". _(Lettering in the image, read by the image model, not confirmed: "57.5%", "42.5%", "FairFace-BW - Generated", "65.7%", "34.3%")_

*Fig. 5 (p. 5):* Gender Distribution of FFHQ training data subsets and generated data : a) gender distribution in training subset, results on GAN and diffusion models trained with b) 300 samples, c) 700 samples, d) 1000 samples, e) 5000 samples, f) 10000 samples — This is a figure of six grouped bar charts arranged in two rows and labeled (a) through (f). Each chart has a vertical axis labeled “Sample %” and a legend with “Male” in blue and “Female” in orange. Chart (a), titled “FFHQ Train,” shows one “Train” group with both bars labeled 50. Charts (b)–(f), titled “FFHQ-300,” “FFHQ-700,” “FFHQ-1k,” “FFHQ-5k,” and “FFHQ-10k,” each show “DDPM” and “GAN” groups side by side with numeric percentage labels on the bars. _(Lettering in the image, read by the image model, not confirmed: “Sample %”, “FFHQ Train,”, “Train”, “FFHQ-300,”, “FFHQ-700,”, “FFHQ-1k,”, “FFHQ-5k,”, “FFHQ-10k,”, “DDPM”)_

*Fig. 6 (p. 5):* Gender Distribution of FairFace-BW training data subsets and generated data : a) gender distribution in training subset, results on GAN and diffusion models trained with b) 300 samples, c) 700 samples, d) 1000 samples, e) 5000 samples, f) 10000 samples — The image is a composite figure of six grouped bar charts arranged in two rows of three, labeled (a)–(f). Each chart has a title such as “FairFace-BW Train,” “FairFace-BW-300,” “FairFace-BW-700,” “FairFace-BW-1k,” “FairFace-BW-5k,” and “FairFace-BW-10k,” a vertical axis labeled “sample %” from 0 to 100, and a legend with blue “Male” and orange “Female.” Chart (a) shows one “Train” category with bars labeled 50 and 50, while charts (b)–(f) show “DDPM” and “GAN” categories with paired blue and orange bars and numeric percentage labels such as 48.33/51.67, 43.89/56.11, 37.76/62.24, 29.7/70.3, and 49.15/50.84. _(Lettering in the image, read by the image model, not confirmed: “FairFace-BW-300,”, “FairFace-BW-700,”, “FairFace-BW-1k,”, “FairFace-BW-5k,”, “FairFace-BW-10k,”, “sample %”, “Train”, “DDPM”)_

*Image 7 (p. 6):* — The image shows six bar charts arranged in a 2x3 grid, labeled (a) through (f), with titles "FairFace-BW Train", "FairFace-BW-300", "FairFace-BW-700", "FairFace-BW-1k", "FairFace-BW-5k", and "FairFace-BW-10k". Each chart has a vertical axis labeled "sample %" ranging from 0 to 100 and displays blue bars for "White" and orange bars for "Black" as indicated in the legend, with numerical values printed above each bar. Chart (a) shows a single x-axis category "Train" with values 50 and 50, while charts (b)-(f) each show two x-axis categories "DDPM" and "GAN" with paired bars for the two groups. _(Lettering in the image, read by the image model, not confirmed: "FairFace-BW-300", "FairFace-BW-700", "FairFace-BW-1k", "FairFace-BW-5k", "FairFace-BW-10k", "Black", "Train", "DDPM")_

*Fig. 8 (p. 6):* Age Distribution of FFHQ training data subsets and generated data : a) age distribution in training subset, results on GAN and diffusion models trained with b) 300 samples, c) 700 samples, d) 1000 samples, e) 5000 samples, f) 10000 samples — The picture shows six grouped bar charts arranged in two rows of three, labeled (a) through (f) beneath each chart. Each chart carries a title at the top—“FFHQ-Train”, “FFHQ-300”, “FFHQ-700”, “FFHQ-1k”, “FFHQ-5k”, and “FFHQ-10k”—and a vertical axis labeled “Sample %” scaled from 0 to 60. A legend titled “Age” lists seven categories—“0-10”, “11-20”, “21-30”, “31-40”, “41-50”, “51-60”, and “>60”—each represented by a differently colored bar, and small numerical values are printed above many of the bars. _(Lettering in the image, read by the image model, not confirmed: “FFHQ-Train”, “FFHQ-300”, “FFHQ-700”, “FFHQ-1k”, “FFHQ-5k”, “FFHQ-10k”, “0-10”, “11-20”, “21-30”, “31-40”, “41-50”, “51-60”, “>60”)_

*Fig. 9 (p. 7):* Data replication in diffusion models : row 2 to 4 present the top-3 matches from the training data. — The picture is a screenshot of a table-like grid of color portrait photographs of human faces. Across the top are the column headings "FFHQ - 300", "FFHQ - 700", and "FFHQ - 1000"; on the left, the top row is labeled "Generated" and the three rows below it are grouped under the label "Training data". Each column group contains two face images per row, so the single generated face in the top row appears above three training-data faces in the rows beneath it.

<!-- quelle: Analyzing Bias in Diffusion-based Face Generation Models (p. 1–9) -->

## LITERATUR

<!-- quelle: References (p. 9–10) -->

- V. Albiero, K. W. Bowyer, and M. C. King. Face regions impact recognition accuracy differently across demographics. In 2022 IEEE International Joint Conference on Biometrics (IJCB) , pages 1-9, 2022.
- V. Albiero, K. Zhang, and K. W. Bowyer. How does gender balance in training data affect face recognition accuracy? In 2020 IEEE International Joint Conference on Biometrics (IJCB) , pages 1-10, 2020.
- V. Albiero, K. Zhang, M. C. King, and K. Bowyer. Gendered differences in face recognition accuracy explained by hairstyles, makeup, and facial morphology. IEEE Transactions on Information Forensics and Security , 17:127-137, 2021.
- S. Azizi, S. Kornblith, C. Saharia, M. Norouzi, and D. J. Fleet. Synthetic data from diffusion models improves imagenet classification. https://arxiv.org/pdf/2304.08466.pdf , 2023.
- F. Boutros, V. Struc, J. Fierrez, and N. Damer. Synthetic data for face recognition: Current state and future prospects. https://arxiv.org/pdf/2305.01021.pdf , 2023.
- J. Buolamwini and T. Gebru. Gender shades: Intersectional accuracy disparities in commercial gender classification. In S. A. Friedler and C. Wilson, editors, Proceedings of the 1st Conference on Fairness, Accountability and Transparency , volume 81 of Proceedings of Machine Learning Research , pages 77-91. PMLR, 23-24 Feb 2018.
- N. Carlini, J. Hayes, M. Nasr, M. Jagielski, V. Sehwag, F. Tram` er, B. Balle, D. Ippolito, and E. Wallace. Extracting training data from diffusion models, 2023.
- J. Choi, J. Lee, C. Shin, S. Kim, H. Kim, and S. Yoon. Perception prioritized training of diffusion models. In 2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) , pages 11462-11471, 2022.
- P. Dhar, J. Gleason, A. Roy, C. D. Castillo, and R. Chellappa. Pass: Protected attribute suppression system for mitigating bias in face recognition. In 2021 IEEE/CVF International Conference on Computer Vision (ICCV) , pages 15067-15076, 2021.
- P. Dhariwal and A. Nichol. Diffusion models beat gans on image synthesis. In M. Ranzato, A. Beygelzimer, Y. Dauphin, P. Liang, and J. W. Vaughan, editors, Advances in Neural Information Processing Systems , volume 34, pages 8780-8794. Curran Associates, Inc., 2021.
- Q. Feng, C. Guo, F. Benitez-Quiroz, and A. Martinez. When do gans replicate? on the choice of dataset size. In 2021 IEEE/CVF International Conference on Computer Vision (ICCV) , pages 6681-6690, 2021.
- I. Goodfellow, J. Pouget-Abadie, M. Mirza, B. Xu, D. Warde-Farley, S. Ozair, A. Courville, and Y . Bengio. Generative adversarial nets. In Z. Ghahramani, M. Welling,
- Cortes, N. Lawrence, and K. Weinberger, editors, Advances in Neural Information Processing Systems , volume 27. Curran Associates, Inc., 2014.
- K. He, X. Zhang, S. Ren, and J. Sun. Deep residual learning for image recognition. In 2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR) , pages 770778, 2016.
- M. Heusel, H. Ramsauer, T. Unterthiner, B. Nessler, and S. Hochreiter. Gans trained by a two time-scale update rule converge to a local nash equilibrium. In I. Guyon, U. V. Luxburg, S. Bengio, H. Wallach, R. Fergus, S. Vishwanathan, and R. Garnett, editors, Advances in Neural Information Processing Systems , volume 30. Curran Associates, Inc., 2017.
- J. Ho, A. Jain, and P. Abbeel. Denoising diffusion probabilistic models. In H. Larochelle, M. Ranzato, R. Hadsell, M. Balcan, and H. Lin, editors, Advances in Neural Information Processing Systems , volume 33, pages 6840-6851. Curran Associates, Inc., 2020.
- J. Ho, C. Saharia, W. Chan, D. J. Fleet, M. Norouzi, and T. Salimans. Cascaded diffusion models for high fidelity image generation. J. Mach. Learn. Res. , 23:47:1-47:33, 2022.
- N. Jain, A. Olmo, S. Sengupta, L. Manikonda, and S. Kambhampati. Imperfect imaganation: Implications of gans exacerbating biases on facial data augmentation and snapchat face lenses. Artificial Intelligence , 304:103652, 2022.
- T. Karras, M. Aittala, J. Hellsten, S. Laine, J. Lehtinen, and T. Aila. Training generative adversarial networks with limited data. In Proceedings of the 34th International Conference on Neural Information Processing Systems , NIPS'20, Red Hook, NY, USA, 2020. Curran Associates Inc.
- T. Karras, S. Laine, and T. Aila. A style-based generator architecture for generative adversarial networks. pages 43964405, 06 2019.
- P. J. Kenfack, K. Sabbagh, A. R. Rivera, and A. Khan. Repfair-gan: Mitigating representation bias in gans using gradient clipping, 2022.
- D. P. Kingma and M. Welling. Auto-encoding variational bayes. https://arxiv.org/pdf/1312.6114.pdf , 2022.
- B. F. Klare, M. J. Burge, J. C. Klontz, R. W. V order Bruegge, and A. K. Jain. Face recognition performance: Role of demographic information. IEEE Transactions on Information Forensics and Security , 7(6):1789-1801, 2012.
- K. K¨ arkk¨ ainen and J. Joo. Fairface: Face attribute dataset for balanced race, gender, and age for bias measurement and mitigation. In 2021 IEEE Winter Conference on Applications of Computer Vision (WACV) , pages 1547-1557, 2021.
- M.-Y. Liu, X. Huang, J. Yu, T.-C. Wang, and A. Mallya. Generative adversarial networks for image and video synthesis: Algorithms and applications. Proceedings of the IEEE , 109(5):839-862, 2021.
- A. S. Luccioni, C. Akiki, M. Mitchell, and Y. Jernite. Stable bias: Analyzing societal representations in diffusion models, 2023.
- V. H. Maluleke, N. Thakkar, T. Brooks, E. Weber, T. Darrell, A. A. Efros, A. Kanazawa, and D. Guillory. Studying bias
- in gans through the lens of race. In European Conference on Computer Vision (ECCV) , 2022.
- R. Naik and B. Nushi. Social biases through the text-toimage generation lens, 2023.
- R. Rombach, A. Blattmann, D. Lorenz, P. Esser, and B. Ommer. High-resolution image synthesis with latent diffusion models. In 2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) , pages 10674-10685, 2022.
- K. K. S, K. Vangara, M. C. King, V. Albiero, and K. Bowyer. Characterizing the variability in face recognition accuracy relative to race. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops , June 2019.
- C. Saharia, J. Ho, W. Chan, T. Salimans, D. J. Fleet, and M. Norouzi. Image super-resolution via iterative refinement. IEEE Transactions on Pattern Analysis and Machine Intelligence , pages 1-14, 2022.
- G. Somepalli, V. Singla, M. Goldblum, J. Geiping, and T. Goldstein. Diffusion art or digital forgery? investigating data replication in diffusion models. https://arxiv.org/pdf/2212.03860.pdf , 2022.
- S. Tan, Y. Shen, and B. Zhou. Improving the fairness of deep generative models without retraining, 2021.
- J. Vincent. Getty images sues ai art generator stable diffusion in the us for copyright infringement. https://www.theverge.com/2023/2/6/23587393/ai-art-copyright-lawsuit-getty-images-stable-diffusion , 6 Feb 2023.
- M. Wang and W. Deng. Mitigating bias in face recognition using skewness-aware reinforcement learning. In 2020 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) , pages 9319-9328, 2020.
- H. Wu, V. Albiero, K. S. Krishnapriya, M. C. King, and K. W. Bowyer. Face recognition accuracy across demographics: Shining a light into the problem. https://arxiv.org/pdf/2206.01881.pdf , 2023.
- N. Yu, K. Li, P. Zhou, J. Malik, L. Davis, and M. Fritz. Inclusive gan: Improving data and minority coverage in generative models. In Computer Vision - ECCV 2020: 16th European Conference, Glasgow, UK, August 23-28, 2020, Proceedings, Part XXII , page 377-393, Berlin, Heidelberg, 2020. Springer-Verlag.

## GLOSSAR

- **DDPM (Denoising Diffusion Probabilistic Model)** — a generative model that learns data distribution through a T-step Markovian process of adding noise (forward) and iterative denoising from Gaussian noise (reverse).
- **FairFace-BW** — the authors' subset of the FairFace dataset restricted to the 'Black' and 'White' racial categories, containing 28,760 images, used to study racial and gender bias.
- **Perceived attributes** — the gender, race, or age of a subject as measured by classifiers on generated images, rather than objectively determined—chosen because such attributes are shaped by social as well as physical factors.
- **Data replication / memorization** — the tendency of generative models, especially diffusion models trained on small datasets, to reproduce training samples in their outputs.
- **FID (Frechet Inception Distance)** — a metric comparing feature distributions of training and generated images via the Inception network; lower scores indicate higher perceptual quality.
- **Attribute classifier** — a ResNet-18 network fine-tuned on FFHQ or FairFace data used to automatically determine the perceived attribute class of generated face images.
