---
id: vartiainen-et-al-2025-enhancing-childrens-understanding-of-algorithmic-biases-in-and-with-text-to-image-generative-ai
titel: Enhancing children's understanding of algorithmic biases in and with text-to-image generative AI
autor: "Henriikka Vartiainen, Juho Kahila, Matti Tedre, Sonsoles Lopez-Pernas, Nicolas Pope"
jahr: 2025
sprache: en
tier: R
sparten: [medial]
themen: [ai, bias, aesthetic_education, education]
lizenz: "All rights reserved - operator copy, local only; this file is a condensation produced on this platform"
url: "https://doi.org/10.1177/14614448241252820"
status: published
analyzed_at: "2026-07-31T12:13:34.346363+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Enhancing children's understanding of algorithmic biases in and with text-to-image generative AI

## PROFIL

Henriikka Vartiainen and Juho Kahila argue that hands-on, collaborative workshops with text-to-image generative AI can facilitate children's conceptual change from naïve conceptions to data-driven explanations of algorithmic biases. The text sets itself against the lack of pedagogical research on facilitating children's awareness of algorithmic biases, as well as against everyday anthropomorphic conceptions that obscure the black-boxed nature of computational processes. Drawing on Vosniadou's framework of conceptual change, the authors demonstrate that engaging directly with generative models helps students understand how biases embedded in training data sets produce discriminatory outputs. For arts education, this positions text-to-image generative AI not merely as a creative tool, but as a medium for cultivating critical AI literacy and data agency by revealing structural prejudices in visual culture.

## WISSEN

### Problem framing and research questions

AI's deep integration into daily life raises concerns about data-driven decision-making: uneven power relations, surveillance, behavior engineering, and algorithmic biases that prioritize and marginalize. Yet many remain unaware of how computational processes sort, classify, and hierarchize people, places, and objects, shaping what enters the cultural realm. Algorithmic bias arises from data collection, algorithm selection, and developer biases, embedding prejudice in AI systems and producing unfair or discriminatory outputs. Algorithms are not neutral but "mirrors" reflecting creators' values and pre-existing stereotypes from training data; ML-based systems may reinforce societal biases around ethnicity, race, gender, and sexual orientation.

Prior research has examined bias across domains (gender, advertisement, job markets, education, politics), while educational approaches to algorithmic media literacy have focused on children's media use, interpretation, critique of online content, and creative production of digital artifacts. Recognition that youth are active producers stresses introducing AI elements for all, especially as generative AI systems proliferate. Researchers call for new AI literacies and data literacies emphasizing critical assessment of AI technologies and understanding of data creation, processing, and utilization.

The authors position against this gap: to their knowledge, no studies have analyzed children's conceptions of algorithmic bias, nor how to facilitate their awareness of it, particularly in text-to-image generative models. The study addresses this through hands-on workshops (N = 213) with fourth- and seventh-grade students in Finland.

**RQ1:** What kinds of biases do children explore in open-ended learning activities, and how do they explain the causes of algorithmic bias?

**RQ2:** How do children's explanations of algorithmic biases develop in a hands-on collaborative workshop on data-driven AI?

<!-- quelle: Problem framing and research questions -->

### Theoretical background: Conceptual change and AI conceptions

Conceptual change research, rooted in cognitive and constructivist traditions, examines the difficulties children face in developing scientific understanding. A common premise is that children hold *naïve conceptions* or misconceptions derived from everyday experiences. For instance, everyday observations lead people to believe AI is unbiased or lacks ethical dimensions, and both children and adults often hold *anthropomorphic conceptions* of AI, assuming computers think or feel like humans. This is complicated by the *black-boxed* nature of contemporary AI, which obscures underlying processes.

According to Vosniadou, these naïve conceptions are difficult to change when they conflict with scientific explanations, requiring *conceptual changes* such as constructing new ontological categories and epistemological understandings. To learn *data-driven reasoning* and understand algorithmic bias, children must grasp:
- training a system to do a job as opposed to programming it;
- curating samples for training data sets and labeling them;
- interpreting results in brittle and opaque systems;
- understanding that computers do not think or make decisions like humans do;
- understanding that biases that creep into systems can impact individuals and societies in many harmful ways.

While everyday experiences are insufficient for primary school students to form scientific conceptions of AI, hands-on learning confronting children with systematic evidence can support conceptual revision. This is facilitated through social and cultural activities involving dialogical interaction and collaboration. Although collaborative exploration with ML technologies offers a promising entry point for understanding ML principles, no studies have yet examined children's initial conceptions of algorithmic biases and their development through hands-on exploration with generative AI.

<!-- quelle: Theoretical background: Conceptual change and AI conceptions -->

### Text-to-image generative models and ethical concerns

The recent AI boom differs from earlier waves: systems are trained with copious data rather than programmed. This wave rests on massive training data, cheap hardware, algorithmic innovation, and deep learning's capacity to capture cognitive abilities across media types. Since the early 2020s, generative AI has entered creative domains, notably text-to-image generative models—programs taking textual prompts as input and producing corresponding novel images. These models employ neural networks trained on billions of images with textual descriptions scraped from public Internet repositories. Midjourney's progression from v1 to v5.1 over 16 months (Figure 1) demonstrates rapid quality gains.

Current cutting-edge methods are diffusion models: networks fed millions of images with textual labels learn to generate new images based on statistically probable pixel patterns associated with given labels. They generalize to images absent from training data—for instance, synthesizing 'depressed cartoon pug wearing a space suit on the moon, with a bottle of whiskey' (Figure 2) by inferring probable pixel patterns for each prompt element and their combination.

The launch of these platforms triggered backlash. Key ethical concerns: (1) training on publicly available images without curation, consent, or knowledge of image owners, with no individual opt-out; (2) copyright infringement through capacity to replicate styles from art history, pop culture, and individual artists—e.g., Greg Rutkowski's ethereal fantasy style mimicked in tens of thousands of AI-generated images; (3) perpetuation of societal biases and stereotypes favoring or marginalizing groups by ethnicity, gender, sexual orientation, and other attributes; (4) proliferation of fake content threatening journalism and democratic societies.

<!-- quelle: Text-to-image generative models and ethical concerns -->

### Research design and methodology

The study extends long-term co-design and design-based research integrating AI into Finnish schools, using cross-boundary collaboration among researchers, developers, and teachers for iterative design, evaluation, and theory-building. Participants: 209 fourth and seventh graders (12 classes, 12 schools) who submitted assignments from 213 enrolled. Ethics followed TENK (2019) guidelines: municipal research permit, guardian permissions, voluntary participation with withdrawal rights, data processing transparency, and consent for publishing digital artifacts; non-participating students' data excluded; names pseudonymized.

Three workshops (~1.5–2 h each, ~1 week apart, 3 weeks total) were embedded in regular curricular activity during spring 2023. The instructional model positioned students as innovators and ML designers, not consumers, using open-ended group tasks to generate ML solutions for self-chosen real-life problems.

The GenAI Teachable Machine tool scaffolded data-driven reasoning through the ML workflow: collecting relevant data, filtering/cleaning, labeling, training a classifier, linking results to behaviors, and evaluating the model. Key ML concepts introduced: training data, example, class, data curation, input, output, confidence. Children personalized projects with own data (photos, voices, music, artwork, text, animations, graphics) to support AI-related agency; iterative prototyping allowed adding/removing classes, re-curating data, re-training, and changing behaviors. Hands-on data selection gave firsthand experience of how bias enters ML models.

- Workshop 1: basic ML concepts, everyday AI applications, social media data collection risks; groups created open-ended classifiers; homework brainstorming everyday ML-solvable problems.
- Workshop 2: data-driven design; teams selected one app idea, used design templates negotiating app function, data sources, class count, training conditions; 71 apps made (emotional states, dance poses, logos, etc.); taught supervised ML concepts (class, label, sample, training data, input, output, confidence, brittleness) and workflows (posing data-driven problem, data collection, curation/labeling, training, evaluating, re-training, deploying).
- Workshop 3: impact and ethics; group presentations reflecting on design/training process, benefits, risks; algorithmic bias explored via generative AI—researchers explained (1) web scrapers extracting image-text pairs, (2) large-scale training parallels to students' classifiers, (3) shared datasets for recognition and generation, (4) image-text correlation enabling text-to-image generation but introducing training-data biases. Bias exemplified by Midjourney prompting government leaders (elderly white men) and classroom teachers (young white women); children then created images to identify biases themselves.

<!-- quelle: Research design and methodology -->

### Types of biases investigated in student experiments

In an open-ended task, student teams generated images to explore algorithmic biases. While gender bias was part of the teachers' demonstration, students mostly pursued biases beyond that presentation. The prompts students used (Table 2, reproduced in full): Anime, Apple, Athletics, Basketball player, Bullier, Car, Cheerleader, Children, Criminal, Dancer, Dog, Fireman, Football player, Hamster, Horses, Ice hockey player, Jesus, Molester, Nurse, Person, Phone, Poor, Poor human, Principal, Scientist, Soldier, Student, Teacher, Woman.

Gender bias was the most common focus. Fourth graders examining "firefighter" found only men generated; they attributed this to online image distribution and proposed a data-driven solution: uploading more photos of women firefighters. Another fourth-grade group found only boy bullies generated but attributed the problem to user prompting rather than training data, advising to "write clearer what you seek."

Appearance bias appeared in seventh graders' dog images (all dark, large, floppy-eared), "woman" images (uniform skin tone and hair color, creating "body appearance pressure"), and Jesus images (white despite Middle Eastern origin). Each group traced bias to web image distribution and proposed adding more diverse images to the web.

Age and combined biases emerged: scientists rendered as "sullen old men," poor people as "old men who were dirty," "person" yielding only old people, and cars producing American vintage models. Some groups proposed data-driven solutions (balancing training sets); others did not address causes or solutions. Of 53 written tasks, 41 proposed data-driven solutions recognizing the training data set's role in mitigating over- or under-representation biases.

<!-- quelle: Results: Types of biases investigated -->

### Development of explanations of algorithmic biases

Qualitative content analysis of pre- and post-test responses yielded six categories of explanations of algorithmic bias. Categories 1–4 represent misconceptions or non-explanations; Category 5 is positioned as the best response, attributing bias to training data. Category 6 was reserved for missing submissions.

The full category scheme:

1. **Bias is not explained** — no explanation, only harms discussed, or simplistic attribution (e.g., 'AI is not very advanced'). Most frequent pre-test response (38.8%), declining to 23.7% post-test.
2. **Bias is attributed to human thinking or actions** — societal prejudices or stereotypes without reference to training data (e.g., 'some people think that soccer is a boys' game'). 35.7% pre-test, 23.2% post-test.
3. **Bias is attributed to creators or users of AI systems** — design choices or prompting without reference to training data (e.g., 'the maker of AI thought that only boys play soccer'). 5.1% pre-test, 1.6% post-test.
4. **Bias is attributed to anthropomorphized AI** — human-like cognitive traits attributed to AI (e.g., 'AI thinks that only boys play soccer'). 13.3% pre-test, 7.7% post-test.
5. **Bias is attributed to training the AI** — over- or under-representation of groups in training data (e.g., 'the web has more pictures where boys play'). Scant in pre-test (7.1%), rising sharply to 43.8% post-test, with some students deploying ML concepts such as training process and samples.
6. **Missing** — no submission.

Transition analysis showed that for all categories except Category 5, the majority of children changed their explanation type between pre- and post-test, with most switching to Category 5. A chi-square test confirmed a statistically significant increase in Category 5 responses from pre- to post-test with a medium effect size.

<!-- quelle: Results: Development of explanations of algorithmic biases -->

### Discussion and implications

The study addresses the lack of research on facilitating awareness of algorithmic biases among children, investigating how they explain biases (focusing on training data) and how this understanding evolves.

First, pre-test analysis revealed five categories of conceptions. Initially, children lacked data-driven explanations (7.1%), with 38.8% providing no explanation. One in three attributed biases to human actions (e.g., gender-based inequality), applying pre-existing societal conceptions. Others cited design choices (5.1%) or anthropomorphized AI (13.3%). While touching root causes, this indicated a lack of understanding of how AI systems learn from data.

Second, post-test results indicated conceptual change through hands-on activities. Data-driven explanations increased to 43.8%. However, incomplete explanations persisted, showing everyday preconceptions can hinder adopting a scientific explanatory framework. Data-driven reasoning relies on a framework very different from everyday experience.

Third, instructional activities promoting conceptual change facilitated understanding. Through hands-on learning and creative making, student teams explored gender biases in AI-generated images (professions, sports, wealth disparities). With teacher guidance, they reflected on everyday experiences from a new perspective, proposing data-driven solutions and recognizing training data sets' role in mitigating over-, mis-, or under-representations.

Overall, systematic instruction and pedagogical approaches are required to base understanding on actual biasing mechanisms (data bias). Understanding ML mechanisms facilitates critical reflection on societal and ethical implications of AI.

<!-- quelle: Discussion and implications -->

## GLOSSAR

- **algorithmic bias** — Prejudice embedded in AI systems arising from data collection, algorithm selection, and developer biases, producing unfair or discriminatory outputs toward specific groups.
- **AI literacies** — Digital competences enabling people to critically assess AI technologies and understand data creation, processing, and utilization.
- **data literacies** — Competences for engaging constructively, critically, responsibly, and safely with practices of a data-driven society.
- **naïve conceptions** — Everyday belief systems or misunderstandings that conflict with scientific explanations and are difficult to change.
- **anthropomorphic conceptions** — The assumption that computers think, act, or feel like humans when making decisions.
- **conceptual changes** — The construction of new ontological categories, representations, and epistemological understandings required to shift intuitive understanding.
- **text-to-image generative models** — Programs that take textual descriptions (prompts) as input and produce corresponding images as output.
- **diffusion models** — Neural networks trained on millions of image-text pairs that generate new images by inferring statistically probable pixel patterns associated with textual labels.
- **prompts** — Textual descriptions provided by users as input to text-to-image generative models to specify the desired output image.
- **design-based research** — A collaborative, iterative research approach engaging researchers, developers, and teachers in parallel processes of design, evaluation, and theory-building.
