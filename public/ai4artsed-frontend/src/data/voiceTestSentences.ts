/**
 * Constructed test sentences for the voices comparison.
 *
 * Not prompts. The page compares how three machines are asked for a voice and
 * a feeling, and that comparison only holds if what the TEXT contributes is
 * known — so what is offered here are sentences built to a stated criterion,
 * and typing your own stays possible rather than being the starting point.
 *
 * TWO AXES
 *
 * `neutral` — everyday sentences built to carry no emotional bias, so that
 * everything heard comes from the machine. `emotional` — the same everyday
 * register, but the sentence carries a feeling, and one word decides which.
 *
 * The emotional eleven are one sentence with one word exchanged, running from
 * the most positive to the most negative. That is what makes them usable: the
 * length and the syntax hold still, so a difference between two takes is the
 * difference between two words and not between two sentences. **Every language
 * has to keep that property.** A translation that varies the sentence around
 * the word destroys the instrument, however well it renders the meaning.
 *
 * THE SAME MATTER IN EVERY LANGUAGE
 *
 * These sentences are built, not quoted, so there is no licensing reason and
 * no provenance reason for one language to have them and another not to. Every
 * platform language is to carry the same two sets, so that the same thing can
 * be checked in each. German and English are here; the other eight are
 * commissioned in `WORK_ORDERS.md` (WO-2026-08-14-E) and appear as they land.
 *
 * ON THE ATTRIBUTION
 *
 * The neutral sentences are modelled on EmoDB, not quoted from it: two of its
 * ten were dropped and one was changed, because they carried gendered
 * references that the criterion never intended. So they are shown as "after".
 * The one Spanish sentence below IS a quotation and is shown without that
 * qualifier — it is the only quoted sentence on the page.
 *
 * These strings are DATA in a particular language, not interface text. They do
 * not go through `en.ts`: an English original translated into German would not
 * be the German sentences, which are the ones this page was built on.
 */

export type TestAxis = 'neutral' | 'emotional' | 'tale'

export interface TestSentence {
  /** Stable id, prefixed with the language it belongs to. */
  id: string
  language: string
  axis: TestAxis
  /** The sentence, in its own language. */
  text: string
  /** Who built it, and to what criterion. Shown with the sentence. */
  source: string
  /** True where the sentence is modelled on that source rather than quoted. */
  after?: boolean
  /**
   * The work's own title, where the entry is one. A long text cannot be its
   * own name in a list - the drop-down shows this instead of the first line of
   * it, and only entries with a title are read as a work rather than as a
   * built sentence.
   */
  title?: string
}

/**
 * The two built sets, per language.
 *
 * `neutral` — five everyday sentences carrying no emotional bias.
 * `emotional` — eleven times one sentence, one word exchanged, ordered from
 * the most positive to the most negative. The order is the axis and is the
 * same in every language; the wording is each language's own.
 */
interface BuiltSets {
  neutral: string[]
  emotional: string[]
}

const FILM_ADJECTIVES_DE = [
  'schönste',
  'spannendste',
  'lustigste',
  'berührendste',
  'interessanteste',
  'uninteressanteste',
  'rätselhafteste',
  'skurrilste',
  'traurigste',
  'schrecklichste',
  'widerlichste',
] as const

const FILM_ADJECTIVES_EN = [
  'most beautiful',
  'most exciting',
  'funniest',
  'most moving',
  'most interesting',
  'least interesting',
  'most puzzling',
  'most bizarre',
  'saddest',
  'most horrifying',
  'most disgusting',
] as const

export const BUILT: Record<string, BuiltSets> = {
  // After Burkhardt, Paeschke, Rolfes, Sendlmeier, Weiss: "A Database of German
  // Emotional Speech", Interspeech 2005, TU Berlin. CC0-1.0. §5 of the paper:
  // everyday sentences "interpretable in the emotions under review and that
  // they contain no emotional bias", built so that every elision and
  // assimilation is possible and as many vowels as possible occur.
  //
  // Five of the ten are not here. a04, b03 and b09 carry gendered references —
  // "ihm", "Agnes", "Karl". a02 ("Das will sie am Mittwoch abgeben") and b01
  // ("Was sind denn das für Tüten…") went the same way: the first hands a woman
  // an errand, the second is a reproach. b10 opened "Die wird…" and now opens
  // "Das wird…", which is why this is "after" EmoDB and not EmoDB.
  de: {
    neutral: [
      'Der Lappen liegt auf dem Eisschrank.',
      'Das schwarze Stück Papier befindet sich da oben neben dem Holzstück.',
      'In sieben Stunden wird es soweit sein.',
      'Sie haben es gerade hochgetragen und jetzt gehen sie wieder runter.',
      'Das wird auf dem Platz sein, wo wir es immer hinlegen.',
    ],
    emotional: FILM_ADJECTIVES_DE.map(
      (adjective) => `Das ist der ${adjective} Film, den ich seit langem gesehen habe.`
    ),
  },
  en: {
    neutral: [
      'The cloth is lying on the fridge.',
      'The black piece of paper is up there next to the piece of wood.',
      'In seven hours the time will have come.',
      'They have just carried it upstairs and now they are going back down.',
      'It will be in the place where we always put it.',
    ],
    emotional: FILM_ADJECTIVES_EN.map(
      (adjective) => `That is the ${adjective} film I have seen in a long time.`
    ),
  },
}

// The citation, and nothing beyond it. What the sentences were built for is
// said by the heading above them (SUPPLIED WORDING); a second sentence
// underneath would be a subtitle nobody asked for.
const NEUTRAL_SOURCE = 'EmoDB (TU Berlin, Interspeech 2005), CC0-1.0'

/** The one quoted sentence on the page. */
const QUOTED: TestSentence[] = [
  {
    // García-Cuesta et al., EmoMatchSpanishDB, Multimedia Tools and
    // Applications 83(5), 2024. Twelve Spanish sentences "created without
    // emotional semantic connotation to avoid any emotional influence in the
    // speaker", covering all Spanish phonemes, about two seconds each — the
    // same construction logic as EmoDB, applied independently to Spanish. One
    // of the twelve is published in its wording; this is that one.
    id: 'es-emomatch-1',
    language: 'es',
    axis: 'neutral',
    text: 'El médico dijo a tu padre que no tome más vino.',
    source: 'EmoMatchSpanishDB (García-Cuesta et al. 2024)',
  },
]

function builtFor(language: string): TestSentence[] {
  const sets = BUILT[language]
  if (!sets) return []
  return [
    ...sets.neutral.map((text, at) => ({
      id: `${language}-neutral-${at + 1}`,
      language,
      axis: 'neutral' as TestAxis,
      text,
      source: NEUTRAL_SOURCE,
      after: true,
    })),
    // No source line: these are built here, so there is nothing to cite.
    ...sets.emotional.map((text, at) => ({
      id: `${language}-emotional-${at + 1}`,
      language,
      axis: 'emotional' as TestAxis,
      text,
      source: '',
    })),
  ]
}

/**
 * ONE TALE PER LANGUAGE, NEVER A TRANSLATION
 *
 * The built sentences above are the same matter in every language, because
 * they are built and can be. A long text is the opposite case: what it tests
 * is prosody over twenty lines - how a machine carries a subordinate clause,
 * where it lifts the voice for direct speech, whether it holds a rhythm - and
 * that is a property OF a language, not of a meaning. A German tale of 1819 in
 * translation would be a German text in borrowed clothes, and what would be
 * heard is the translation.
 *
 * So every language gets a tale of its own, out of its own public domain,
 * chosen against the same criterion: long enough to hear a rhythm, exciting,
 * harmless, the first sequence ending well, and a citable source.
 *
 * WHAT THAT COSTS, AND WHY THE SET IS NOT OF ONE KIND
 *
 * Folk-tale COLLECTIONS from before 1930 are field transcriptions in dialect,
 * by design - that is what collecting was. Grimm and Jacobs are speakable only
 * because their editors had already regularised. Where nobody did, public
 * domain and speakable pull against each other: a dialect notation read by a
 * machine built for the standard is a comparison of notations, not of voices.
 * A first Bulgarian candidate went back for exactly that, and a second reason:
 * it was recorded in Ohrid, and an entry labelled simply "Bulgarian" would have
 * taken a side in a contested question without anyone deciding to.
 *
 * So where that happens, the entry is a named author's own version of a tale of
 * that language, and says so. Collected: German, English, Spanish, Ukrainian,
 * Turkish. An anonymous classical text: Arabic. A named author's version:
 * Hebrew (Bialik), Bulgarian (Elin Pelin). The set is mixed in kind on purpose,
 * and the source line always says which.
 *
 * KOREAN IS THE EXCEPTION: after the search had run its course, the Korean
 * entry became the paragraph of the Bremen Town Musicians, translated here.
 *
 * What the search established is why. A traditional tale is nobody's property
 * - that part was never in doubt, and treating it as a rights question was an
 * error corrected on the way. But in Korea every ACCESSIBLE modern rendering
 * turns out to be a named person's own text: the children's library portal
 * carries licensed picture books as subtitled video, the open teaching pages
 * carry a lecturer's course prose, the scholarly editions are Choi In-hak's and
 * Shin Won-gi's translations into today's Korean. The one rendering that is
 * both public domain and a Korean's own - Sim Ui-rin's collection of 1926, the
 * first in the language - is not digitised anywhere that can be opened. What is
 * older than that carries no word spacing at all. The oral corpus holds real
 * tellings, but as fieldwork transcripts, with the interviewer in them.
 *
 * So Korean carries the German tale, translated here, and the entry says that
 * on its face. The rule stands for the other nine and stands for Korean too the
 * day a Korean tale can be had: this is a stopgap that names itself, not a
 * quiet exception.
 *
 * Nothing may be written from memory, and nothing may be smoothed: a tale goes
 * in only when its actual text and its actual source are in hand.
 */
const TALES: TestSentence[] = [
  {
    id: 'de-tale-bremen',
    language: 'de',
    axis: 'tale',
    title: 'Die Bremer Stadtmusikanten',
    // The beginning, up to where the four are on the road together: the
    // threats are all announced and none is carried out, and the sequence ends
    // with the four of them walking off. The old spelling is the source's
    // ("giengen", "todt", "theuer", "Rath") and stays - a smoothed one would
    // be a different text.
    text: `Es hatte ein Mann einen Esel, der ihm schon lange Jahre treu gedient hatte, dessen Kräfte aber nun zu Ende giengen, so daß er zur Arbeit immer untauglicher ward. Da wollte ihn der Herr aus dem Futter schaffen, aber der Esel merkte daß kein guter Wind wehte, lief fort und machte sich auf den Weg nach Bremen: 'dort,' dachte er, 'kannst du ja Stadtmusikant werden.' Als er ein Weilchen fortgegangen war, fand er einen Jagdhund auf dem Wege liegen, der jappte wie einer, der sich müde gelaufen hat.' 'Nun, was jappst du so, Packan?' fragte der Esel. 'Ach,' sagte der Hund, 'weil ich alt bin und jeden Tag schwächer werde, auch auf der Jagd nicht mehr fort kann, hat mich mein Herr wollen todt schlagen, da hab ich Reißaus genommen; aber womit soll ich nun mein Brot verdienen?' 'Weißt du was,' sprach der Esel, 'ich gehe nach Bremen, dort Stadtmusikant zu werden, geh mit und laß dich auch bei der Musik annehmen. Ich spiele die Laute, und du schlägst die Pauken.' Der Hund wars zufrieden, und sie giengen weiter. Es dauerte nicht lange, so saß da eine Katze an dem Weg und machte ein Gesicht wie drei Tage Regenwetter. 'Nun, was ist dir in die Quere gekommen, alter Bartputzer?' sprach der Esel. 'Wer kann da lustig sein, wenns einem an den Kragen geht,' antwortete die Katze, 'weil ich nun zu Jahren komme, meine Zähne stumpf werden, und ich lieber hinter dem Ofen sitze und spinne, als nach den Mäusen herum jage, hat mich meine Frau ersäufen wollen, ich habe mich zwar noch fortgemacht, aber nun ist guter Rath theuer: wo soll ich hin?' 'Geh mit uns nach Bremen, du verstehst dich doch auf die Nachtmusik, da kannst du ein Stadtmusikant werden.' Die Katze hielt das für gut und gieng mit. Darauf kamen die drei Landesflüchtigen an einem Hof vorbei, da saß auf dem Thor der Haushahn und schrie aus Leibeskräften. 'Du schreist einem durch Mark und Bein,' sprach der Esel, 'was hast du vor?' 'Da hab ich gut Wetter prophezeit,' sprach der Hahn, 'weil unserer lieben Frauen Tag ist, wo sie dem Christkindlein die Hemdchen gewaschen hat und sie trocknen will: aber weil Morgen zum Sonntag Gäste kommen, so hat die Hausfrau doch kein Erbarmen, und hat der Köchin gesagt sie wollte mich Morgen in der Suppe essen, und da soll ich mir heut Abend den Kopf abschneiden lassen. Nun schrei ich aus vollem Hals, so lang ich noch kann.' 'Ei was, du Rothkopf,' sagte der Esel, 'zieh lieber mit uns fort, wir gehen nach Bremen, etwas besseres als den Tod findest du überall; du hast eine gute Stimme, und wenn wir zusammen musicieren, so muß es eine Art haben.' Der Hahn ließ sich den Vorschlag gefallen, und sie giengen alle viere zusammen fort.`,
    source: 'Br\u00fcder Grimm, Kinder- und Hausm\u00e4rchen, KHM 27',
  },
  {
    id: 'en-tale-whittington',
    language: 'en',
    axis: 'tale',
    title: 'Whittington and His Cat',
    // Up to where a stranger takes the boy on for work in the hay-field. The
    // ill-tempered cook comes after that and is left out: her threats are made
    // good on, and the criterion is that nothing cruel is carried out. The
    // comma in "he, sat down" is the source's and stays.
    text: `In the reign of the famous King Edward III. there was a little boy called Dick Whittington, whose father and mother died when he was very young. As poor Dick was not old enough to work, he was very badly off; he got but little for his dinner, and sometimes nothing at all for his breakfast; for the people who lived in the village were very poor indeed, and could not spare him much more than the parings of potatoes, and now and then a hard crust of bread. Now Dick had heard a great many very strange things about the great city called London; for the country people at that time thought that folks in London were all fine gentlemen and ladies; and that there was singing and music there all day long; and that the streets were all paved with gold. One day a large waggon and eight horses, all with bells at their heads, drove through the village while Dick was standing by the sign-post. He thought that this waggon must be going to the fine town of London; so he took courage, and asked the waggoner to let him walk with him by the side of the waggon. As soon as the waggoner heard that poor Dick had no father or mother, and saw by his ragged clothes that he could not be worse off than he was, he told him he might go if he would, so off they set together. So Dick got safe to London, and was in such a hurry to see the fine streets paved all over with gold, that he did not even stay to thank the kind waggoner; but ran off as fast as his legs would carry him, through many of the streets, thinking every moment to come to those that were paved with gold; for Dick had seen a guinea three times in his own little village, and remembered what a deal of money it brought in change; so he thought he had nothing to do but to take up some little bits of the pavement, and should then have as much money as he could wish for. Poor Dick ran till he was tired, and had quite forgot his friend the waggoner; but at last, finding it grow dark, and that every way he turned he saw nothing but dirt instead of gold, he, sat down in a dark corner and cried himself to sleep. Little Dick was all night in the streets; and next morning, being very hungry, he got up and walked about, and asked everybody he met to give him a halfpenny to keep him from starving; but nobody stayed to answer him, and only two or three gave him a halfpenny; so that the poor boy was soon quite weak and faint for the want of victuals. In this distress he asked charity of several people, and one of them said crossly: "Go to work, for an idle rogue." "That I will," says Dick, "I will to go work for you, if you will let me." But the man only cursed at him and went on. At last a good-natured looking gentleman saw how hungry he looked. "Why don't you go to work my lad?" said he to Dick. "That I would, but I do not know how to get any," answered Dick. "If you are willing, come along with me," said the gentleman, and took him to a hay-field, where Dick worked briskly, and lived merrily till the hay was made.`,
    source: 'Joseph Jacobs, English Fairy Tales, London 1890',
  },
  {
    id: 'es-tale-pajaro',
    language: 'es',
    axis: 'tale',
    title: 'El pájaro de la verdad',
    // Up to where the birds teach the twins their language. What comes after is
    // the foster-siblings' taunting; here the jealousy is named and nothing is
    // shown, and the sequence closes on the two finding where they belong.
    text: `Érase vez y vez un pescador muy pobre, que vivía en una chocita en la orilla de un río, muy claro, muy manso, aunque profundo, el que huyendo del sol y la bulla, se entraba por entre árboles, zarzas y cañaverales a escuchar a los pajaritos que le alegraban con sus cantos. Un día que, metido en su lanchita, iba el pescador a echar sus redes, vio bajar pausadamente por la corriente una arquita de cristal. Bogole al encuentro, y ¡cuál no sería su asombro al ver en ella acostadas sobre algodones a dos criaturas recién nacidas, niño y niña, al parecer mellizos! Al pobre pescador le dio mucha lástima de ellas y se las llevó a su mujer, que a la sazón estaba criando. -¡Eso es! -dijo esta cuando se los presentó-. Tenemos ocho hijos, y como si no tuviésemos bastantes, me traes unos pocos más. -Mujer -repuso el pobre pescador-, ¿y qué hacía?... ¿Dejaba ir sin projimidad ni caridad ninguna a estos angelitos río abajo, a que se muriesen de hambre o a que se los tragase la mar con sus grandes tragaderas? ¡Dios, que nos envía estos dos hijitos más, cuidará de ayudarnos a criarlos! Y así sucedió; porque los niños se criaron sanos y robustos a la par de sus otros ocho hijos. Eran ambos tan buenos, tan dóciles y tan compuestitos, que el pescador y su mujer los querían mucho, y de continuo se los ponían por ejemplo a sus otros hijos, por lo cual estos, envidiosos y enrabiados, les hacían mil injusticias y mil agravios; de manera que huyendo de estos vejámenes, se iban los huérfanos a refugiar entre las arboledas y cañaverales de las orillas del río. Divertíanse con los pajaritos, a los que llevaban migajas de pan, y estos, agradecidos, volaban a su encuentro y les enseñaban la lengua de los pájaros, que aprendieron pronto; y así se entretenían con ellos y les enseñaron muchas cosas muy buenas y muy bonitas, siendo una de ellas el levantarse temprano y otra el cantar.`,
    source: 'Fernán Caballero, Cuentos, adivinanzas y refranes populares',
  },
  {
    id: 'ar-tale-sindbad',
    language: 'ar',
    axis: 'tale',
    title: 'حكاية السندباد البحري',
    // The porter at the gate, up to the end of his poem. The frame story of the
    // Nights is not usable and is not here; this is the opening of the embedded
    // tale, which is attested in the Arabic manuscripts - unlike Aladdin and
    // Ali Baba, which reached Arabic only after Galland. The poem's hemistichs
    // are separated in the source by column rules; here by a space.
    text: `قالت: بلغني أنه كان في زمن الخليفة أمير المؤمنين هارون الرشيد بمدينة بغداد رجل يقال له السندباد الحمال، وكان رجلاً فقير الحال يحمل تجارته على رأسه فاتفق له أنه حمل في يوم من الأيام حملة ثقيلة، وكان ذلك اليوم شديد الحر فتعب من تلك الحملة وعرق واشتد عليه الحر، فمر على باب رجل تاجر قدامه كنس ورش وهناك هواء معتدل، وكان بجانب الباب مصطبة عريضة فحط الحمال حملته على تلك المصطبة ليستريح ويشم الهواء. وأدرك شهرزاد الصباح فسكتت عن الكلام المباح. وفي الليلة الواحدة والثلاثين بعد الخمسمائة قالت: بلغني أيها الملك السعيد، أن الحمال لما حط حملته على تلك المصطبة ليستريح ويشم الهواء خرج عليه من ذلك الباب نسيم رائق ورائحة ذكية، فاستلذ الحمال لذلك وجلس على جانب المصطبة، فسمع في ذلك المكان نغم أوتار وعود وأصوات مطربة وأنواع إنشاد معربة، وسمع أيضاً أصوات طيور تناغي وتسبح الله تعالى باختلاف الأصوات وسائر اللغات، من قماري وهزار وشحارير وبلابل وفاخت وكروان. فعند ذلك تعجب من نفسه وطرب طرباً شديداً، فتقدم إلى ذلك فوجد داخل البيت بستاناً عظيماً. ونظر فيه غلماناً وعبيداً وخداماً وحشماً وشيئاً لا يوجد إلا عند الملوك والسلاطين وبعد ذلك هبت عليه رائحة أطعمة طيبة ذكية من جميع الألوان المختلفة والشراب الطيب فرفع طرفه إلى السماء وقال: سبحانك يا رب، يا خالق، يا رزاق، ترزق من تشاء بغير حساب اللهم إني أستغفرك من جميع الذنوب وأتوب إليك من العيوب يا رب لا أعترض عليك في حكمك وقدرتك فإنك لا تسأل عما تفعل وأنت على كل شيء قدير سبحانك تغني من تشاء وتعز من تشاء وتذل من تشاء لا إله إلا أنت ما أعظم شأنك وما أقوى سلطانك وما أحسن تدبيرك، قد أنعمت على من تشاء من عبادك فهذا المكان صاحبه في غاية النعمة، وهو متلذذ بالروائح اللطيفة والمآكل اللذيذه، والمشارب الفاخرة في سائر الصفات وقد حكمت في خلقك بما تريد وما قدرته عليهم، فمنهم تعبان ومنهم مستريح ومنهم سعيد ومنهم من هو مثلي في غاية التعب والذل، وأنشد يقول: فكم من شـقـي بـلا راحة ينعم في خير فـيء وظـل وأصبحت فـي تـعـب زائد وأمري عجيب وقد زاد حملي وغيري سعيد بـلا شـقـوة وما حمل الدهر يوماً كحملي ينـعـم فـي عـيشة دائمـاً ببسط وعز وشـرب وأكـل وكل الخلائق مـن نـطـفة أنا مثل هذا وهذا كمثـلـي ولكن شتـان مـا بـينـنـا وشتان بين خـمـر وخـل ولست أقول عليك افـتـراء فأنت حكيم حكمت بـعـدل`,
    source: 'ألف ليلة وليلة — طبعة بولاق ١٨٣٥',
  },
  {
    id: 'he-tale-shlomo',
    language: 'he',
    axis: 'tale',
    title: 'שלמה והתור המתהלל',
    // Not a collected tale but Bialik's own literary version of an aggadic
    // legend, and named as his. The whole short piece, vowelled as he set it.
    // Two oddities of the printed text are left standing.
    text: `וַיְהִי הַיּוֹם ושְׁלֹמֹה יוֹשֵׁב בְּאַרְמוֹנוֹ עַל־יַד הַחַלּוֹן וּפָנָיו אֶל הַגָּן. וּמִמַּעַל לְמַשְקוֹף הַחַלּוֹן, בְּפִנַּת גָּג, אֲרֻבַּת יוֹנִים קְטַנָּה, קַן־מִבְטַחִים לְתוֹר וּבַת־זוּגוֹ. וַיָּבֹא בְּאָזְנֵי הַמֶּלֶך קוֹל הַתּוֹר בַּהֲגוֹתוֹ לַחֲבֶרְתּוֹ לֵאמֹר: "יוֹנָתִי, הֲשַׂמְתְּ לִבֵּך אֶל הַאַרְמוֹן הֶָּזה אֲשֶׁר לַמֶּלֶךְ? הֲלֹא שַׂגִּיא וְנִשְׂגָּב הוּא בְעֵינַיִךְ, וְאוּלָם בְּעֵינַי – כָּמֹהוּ כְּרֹאש שִׁבֹּלֶת. לוּא הוֹאַלְתִּי וְאֶפְגַּע בּוֹ בִּקְצֵה מַקּוֹרִי – וְנֶהְפַּךְ כְּרֶגַע לְאִי מַפָּלָה. פִּיד אֶחָד – וְהָיָה כְלֹא הָיָה." וַיִּשְׁלַח הַמֶּלֶך את רֹאשׁוֹ מן הַחַלּוֹן, וּבִרְאוֹתוֹ את פוֹשֵׂק הַשְׂפָתַיִם קְרָאוֹ אֵלָיו וַיֹּאמֶר בְּזַעַף: "אִי, קְצַר־אֶבְרָה וּרְחַב־פֶּה! הַאַתָּה תִּתֹּץ אֶת־אַרְמוֹנִי? אֵיכָכָה לֹא־בֹשְׁתָּ לְהִתְהַלֵּל בַּשָּוְא?" מִגַעֲרָת הַמֶּלֶך נִחַת הַתּוֹר, כִּמְעַט הִתְעַלֵּף, וְאוּלָם עַד מְהֵרָה מָצָא אֶת־לִבּוֹ וַיֹאמַר: "חָכְמָתְךָ תִּסְעָדֵנִי, אֲדוֹנִי הַמֶּלֶךְ! לְךָ הַבִּינָה וְעִמְּךָ הַחֲנִינָה. כִּי לִפְנֵי מִי הִתְהַלַּלְתִּי? הֲלּא לִפְנֵי אִשְׁתִּי. הֲיֶחֱטָא בַעַל בְּהִתְפָּאֲרוֹ מְעַט לִפְנֵי אִשְׁתּוֹ?" וַיִּשְׂחַק הַמֶּלֶךְ לְמַעֲנֵה הַתּוֹר וִיִּפְטְרֵהוּ בְשָׁלוֹם, וְאוּלָם הָעֵד הֵעיד בּוֹ לְבִלְתִּי יִשְׁנֶה עוֹד בְּאִוַּלְתּוֹ וְאֶת־פִּיו וּלְשׁוֹנוֹ יִשְׁמֹר.ִ וַיְהִי אַך שָׁב הַתּוֹר אֶל שׁוֹבַכּוֹ, וּשְׁלֹמֹה שׁוֹמֵעַ שֵנִית: "תַּמָּתִי, הֲיָדַעַתְּ לָמָה קָרָא לִי הַמֶּלֶךְ? הַטִּי אָזְנֵךְ וְאֶלְחַשׁ לָךְ: הַפֵּל הִפִּיל לְפָנַי אֶת־תְּחִנָּתוֹ, כִּי אָחוּס עַל אַרְמוֹנוֹ וְלֹא אַשְׁחִיתֶנוּ, כִּי עַל כֵּן אַרְמוֹן מֶלֶך הוּא וְרַבַּת עָמְלוּ בוֹנִיו בּוֹ. וַאֲנִי גַם אֲנִי, כְּשָׁמְעִי קוֹל תַּחֲנוּנָיו, רַךְ לבָבִי וָאֶשָּׂא פָּנָיו. הִנֵּה כָזֹאת וְכָזֹאת שָׁאַל מֵעִמִּי הַמֶּלֶך וְכָזֹה וְכָזֶה עֲנִיתִיו. מָה הַדָּבָר בְּעֵינַיִךְ יָפָתִי?" כִּשְׁמֹע הַמֶּלֶךְ אֶת־דִּבְרֵי הַתּוֹר לֹא רָגַז עוֹד וְלֹא שָׂחַק, כִּי אָמַר בְּיָגוֹן: נָקֵל לְהַכְרִיעַ שִׁבְעָה יְצָרִים גְּדוֹלִים מֵהַכְרִיעַ יֵצֶר אֶחָד קָטָן.`,
    source: 'ח״נ ביאליק, ויהי היום — מאגדות המלך שלמה',
  },
  {
    id: 'uk-tale-korabel',
    language: 'uk',
    axis: 'tale',
    title: 'Летючий корабель',
    // Up to where the old man has told him how to get the ship. The mother's
    // "the wolves will eat you" is said and never happens, which is the shape
    // the criterion asks for. Rudchenko's own spelling and his » « stay.
    text: `Був собі дід і баба, а в них було три сини: два розумних, а третій дурний. Розумних же вони й жалують, баба їм що-неділі білі сорочки дає, а дурника всі лають, сміються з нього — а він, знай, на печі у просі в чорній сорочці, без штанців… Як дадуть, то й їсть; а ні, то він і голодує. Аж от прийшла чутка, що так і так: прилетів такий царський указ, щоб зібралися до царя на обід, і хто построїть такий корабель, щоб літав, і приїде на тім кораблї, за того царь дочку оддає. Розумні браті й радяться: »Піти б, то, може, там де наше щастя закотилося!« Порадились, просяться в батька та в матері: »Підемо ми«, кажуть, »до царя на обід: загуби́ть — нічого не загубимо, а, може, там де наше щастя закотилося!« Батько їх умовляє, мати їх умовляє… Ні! »Підем, та й годі! Благословіть нас на дорогу.« Старі — нічого робить, — взяли, поблагословили їх на дорогу, баба надавала їм білих паляниць, спекла порося, пляшку горілки дала, — пішли вони. А дурень сидить на печі, та й собі проситься: »Піду й я туди, куди брати пішли!« — »Куди ти, дурню, підеш?« каже мати, »там тебе й вовки ззідять!« — »Ні«, каже, »не ззідять: піду!« Старі з його зпершу сміялись, а то давай лаяти. Так ні! Вони бачать, що́ з дурнем, мовляв, зробиш! — та й кажуть: »Ну йди, та щоб ти вже й не вертався й щоб не признавався, що ти наш і син.« Баба дала йому торбу, наклала туди чорного черствого хліба, пляшку води дала й випровадила його з дому. Він і пішов. Іде та йде, — коли зустрічає на дорозі діда: такий сивий дідуган, борода зовсім біла, аж до поясу! — Здорові, діду! — Здоров, сину! — Куди йдете, діду? А той каже: — »Ходжу по світу: з біди людей виручаю. А ти куди?« — До царя на обід. »Хиба ти«, пита дід, »умієш зробити такий корабель, щоб сам літав?« — Ні, каже, не вмію! »То й чого ж ти йдеш?« — А Бог його знає, — каже, — чого! Загубити — не загублю, а може там де моє щастя закотилося. »Сідай же«, каже, »та спочинеш трохи, пополуднуємо. Виймай, що там у тебе в торбі!« — Е, дідусю, нема тут нічого, самий черствий хліб, що ви й не вкусите. »Нічого, виймай!« От дурень виймає — аж з того чорного хліба та такі стали паляниці білі, що він ізроду й не їв таких: сказано, як у панів. — »Ну, що ж«, — каже дід — »як його, не пивши, полуднувати? Чи немає там у тебе в торбі горілки? — Де б то вона в мене взялась! Є тільки води пляшка! »Виймай!« — каже. Він вийняв, покуштував — аж там така горілка стала! »От, бач«, каже дід: »як Бог дурнів жалує!« От вони розіслали свитки на траві, посідали — давай полуднувати. Пополуднували гарненько, подякував дід дурневі за хліб, за горілку, та й каже: »Ну, слухай сину: йди ж тепер ти в ліс та підійди до дерева та перехрестися тричі й ударь сокирою в дерево, а сам мерщій падай ниць і лежи, аж поки тебе хто не розбудить: тоді«, каже, »тобі корабель збудується, а ти сідай на нього й лети, куди тобі треба, по дорозі бери, кого б там не стрів.« Дурень подякував дідові, й розпрощалися: дід пішов своєю дорогою, а дурень пішов у ліс.`,
    source: 'Українські народні казки, зі збірника Івана Рудченка, 1920',
  },
  {
    id: 'fr-tale-fees',
    language: 'fr',
    axis: 'tale',
    title: 'Les Fées',
    // Up to the mother calling her "ma fille" for the first time. The spelling
    // is Barbin's of 1697 and stays ("estoit", "aisnée", "honnesteté"); the
    // printed & stays a & and is left to each machine to do with as it does.
    text: `Il estoit une fois une Veuve qui avoit deux filles : l'aisnée luy ressembloit si fort d'humeur et de visage, que qui la voyoit, voyoit la mere. Elles estoient toutes deux si desagreables et si orgueilleuses, qu'on ne pouvoit vivre avec elles. La Cadette, qui estoit le vray portrait de son pere pour la douceur et l'honnesteté, estoit avec cela une des plus belles filles qu'on eust su voir. Comme on aime naturellement son semblable, cette mere estoit folle de sa fille aisnée, et en même temps avoit une aversion effroyable pour la Cadette. Elle la faisoit manger à la Cuisine & travailler sans cesse. Il falloit entre-autre chose que cette pauvre enfant allast deux fois le jour puiser de l'eau à une grande demy lieue du logis, & qu'elle en raportast plein une grande cruche. Un jour qu'elle estoit à cette fontaine, il vint à elle une pauvre femme qui la pria de luy donner à boire ? Ouy da, ma bonne mere, dit cette belle fille, & rainçant aussi-tost sa cruche, elle puisa de l'eau au plus belle endroit de la fontaine, & la lui presenta, soûtenant toûjours la cruche afin qu'elle bût plus aisément. La bonne femme ayant bu, luy dit, vous estes si belle, si bonne, & si honneste, que je ne puis m'empêcher de vous faire un don, (car c'estoit une Fée qui avoit pris la forme d'une pauvre femme de vilage, pour voir jusqu'où iroit l'honnesteté de cette jeune fille.) Je vous donne pour don, poursuivit la Fée, qu'à chaque parole que vous dirés, il vous sortira de la bouche où une Fleur, où une Pierre précieuse. Lorsque cette belle fille arriva au logis, sa mere la gronda de revenir si tard de la fontaine. Je vous demande pardon, ma mere, dit cette pauvre fille, d'avoir tardé si long-temps, & en disant ces mots il luy sortit de la bouche deux Roses, deux Perles, & deux gros Diamants. Que voy je là, dit sa mere toute estonnée, je crois qu'il luy sort de la bouche des Perles & des Diamants, d'où vient cela, ma fille, (ce fut là la premiere fois qu'elle l'appela sa fille.)`,
    source: 'Charles Perrault, Histoires ou contes du temps passé, Paris 1697',
  },
  {
    id: 'bg-tale-jabylka',
    language: 'bg',
    axis: 'tale',
    title: 'Тримата братя и златната ябълка',
    // Not a collected tale but Elin Pelin's own version of a Bulgarian
    // tale-type, and named as his: the collections of his time are dialect
    // transcriptions, and a dialect notation read by a machine built for the
    // standard is a comparison of notations. Up to where both older brothers
    // have been pulled back up unhurt.
    text: `Една жена имала троица синове. В двора имало едно ябълково дърво, което в годината раждало по една златна ябълка. Една хала всяка година дохождала нощно време и открадвала ябълката. Най-старият син рекъл: „Мале, аз ще вардя ябълката.“ Майка му казала: „Е, синко, толкова години не сме я опазили, та сега ли ще я опазим!“ — „Не, ще я опазим“ — казал синът и отишъл да варди. За да не заспи, той взел една торба орехи да троши цяла нощ. Ала той се залисал с орехите, халата дошла и откраднала ябълката. На другата година средният син рекъл на майка си: „Мале, аз ще вардя ябълката.“ Майка му отговорила: „Е, синко, толкова години не сме я опазили, та сега ли ще я опазим!“ — „Не, сега ще я опазим“ — казал синът и отишъл да я пази. За да не заспи, и той взел една торба орехи да чука цяла нощ. Ала и той се залисал с орехите, халата дошла и откраднала ябълката. На третата година най-малкият син рекъл: „Мале дай на мене ножа, аз ще отида да вардя ябълката.“ — „Иди, сине!“ — казала майка му. Той отишъл в градината, качил се на ябълката и се скрил в клоните да чака. Посред нощ се задало нещо като мъгла, зафучало, затрещяло: дошла халата и посегнала да вземе ябълката. Той я ръгнал с ножа и халата избягала. Тогава синът взел ябълката и я занесъл на майка си. След това той поканил братята си да отидат да намерят халата. Като тръгнали по кървавите следи, стигнали до една пещера. Малкият брат казал: „Ха да спуснем едного в пещерата.“ Най-старият брат склонил него да спуснат. Като го спуснали до средата, той се уплашил и заклатил въжето, а другите го измъкнали. Тогава средният склонил него да пуснат; като го спуснали до средата, и той заклатил въжето — и него извадили.`,
    source: 'Елин Пелин, Тримата братя и златната ябълка, 1917',
  },
  {
    id: 'tr-tale-husnu',
    language: 'tr',
    axis: 'tale',
    title: 'Hüsnü Yusuf',
    // Printed as anonymous collected material in the journal of Turkey's first
    // folklore association - no collector is named, which is why the rights
    // rest on the term for anonymous works rather than on a death date. The
    // period spelling of the print is the source's and stays ("nakadar",
    // "bunuda"). Up to where Keloğlan and his mother decide to go too.
    text: `Birvarmış bir yokmuş, evel zaman içinde bir beyin bir kızı varmış. Bu kız günün birinde evinin üstüne çıkarak gergef kurup bir çevre işlemeye başlar. Bir gün çevresini bitirip karşısına koyar, kendi kendine ey bunu işleyen eller der, bu sırada pencereden altun gagalı gümüş ayaklı bir kuş gelip çevreyi alır kaçar. Kız kuşu yakalamak için boynundaki inci kelebeğini kuşa atar, kuş bunuda alır. Kız hem çevresine acır, hem de kuşu sever. Bunun yüzünden kız merak eder, günden güne merakı artar, gece gündüz yemek yemeden durur. Hiç bir kimse kızın derdine derman bulamaz. Bu kızın bir de dadısı varmış, kız bütün derdini dadısına anlatırmış. Bir gün dadısı kızın yanına gider, ne derdi olduğunu sorar. Kız ona başından gelip geçenleri anlatır. Dadı beye koşar, beyim kızınız derdini bana söyledi ve sizden dünyada nakadar kuş varsa getirmenizi istiyor der. Bey dünyada nekadar kuş varsa hepsini getirtir. Kız benim istediğim kuş burada yok, babam bana demir ayakkabı ile demir asâ yaptırsın, ben seyahata çıkacağım der. Babası kızın her şeyini hazırladıktan sonra kız seyahata çıkar. Bir memlekete gelir, orada bir hamam yaptırır ve bu memlekette nekadar dertli kimseler varsa bu hamamda bedava yıkanıp çıktıkları zaman ne dertleri varsa bana söyliyecektir diye dellal çağırtır. Bütün dertliler bu hamamda yıkanıp dertlerini kıza anlatırlar. Bunu işiten fakir kel oğlan annesine haydi biz de bu hamamda yıkanalım der. Anası aman oğlum bizim ne derdimiz var ki ona anlatacağız der. Çocuk olsun ana elbet bir şey söyleriz der.`,
    source: 'Halk Bilgisi Haberleri, Sayı 25, İstanbul 1933',
  },
  {
    id: 'ko-tale-bremen',
    language: 'ko',
    axis: 'tale',
    title: '브레멘 음악대',
    // THE ONE TRANSLATION, and it is one on purpose - see the note above TALES.
    // Made here, from the German, and the source line says so rather than
    // letting a German tale pass for a Korean one. It is not to be translated
    // onward, not smoothed, and not "improved".
    text: `옛날에 어떤 사람이 당나귀 한 마리를 기르고 있었습니다. 당나귀는 여러 해 동안 주인을 충실히 섬겼지만, 이제는 기운이 다하여 일을 하기가 점점 어려워졌습니다. 주인이 먹이를 끊으려 하자, 당나귀는 바람이 심상치 않다는 것을 알아채고 집을 뛰쳐나와 브레멘으로 가는 길에 올랐습니다. '거기에 가면 거리의 악사가 될 수 있겠지.' 하고 당나귀는 생각했습니다. 얼마쯤 걸어갔을 때, 당나귀는 길가에 사냥개 한 마리가 누워서 멀리 달려온 것처럼 헐떡거리고 있는 것을 보았습니다. "이보게, 왜 그렇게 헐떡이고 있나?" 하고 당나귀가 물었습니다. "아이고," 하고 개가 말했습니다. "내가 늙어서 날마다 기운이 빠지고 사냥도 더는 못 하게 되니, 주인이 나를 때려죽이려고 하지 뭔가. 그래서 도망쳐 나왔네. 그런데 이제 무엇으로 밥벌이를 한단 말인가?" "그럼 이렇게 하세." 하고 당나귀가 말했습니다. "나는 브레멘으로 거리의 악사가 되러 가는 길이라네. 함께 가서 자네도 악단에 들어가게. 나는 류트를 타고, 자네는 북을 치면 되지 않겠나." 개는 그것이 좋다고 하여, 둘은 함께 길을 갔습니다. 얼마 가지 않아 길가에 고양이 한 마리가 앉아 있었는데, 사흘 내내 비가 온 것 같은 얼굴을 하고 있었습니다. "이보게, 무슨 일이 그렇게 언짢은가, 늙은 수염 손질꾼?" 하고 당나귀가 말했습니다. "목이 달아나게 생겼는데 누가 즐거울 수 있겠나." 하고 고양이가 대답했습니다. "내가 이제 나이가 들어 이빨도 무디어지고, 쥐를 쫓아다니기보다 난롯가에 앉아 실을 잣는 편이 좋아지니, 주인 아주머니가 나를 물에 빠뜨려 죽이려고 하지 않겠나. 겨우 빠져나오기는 했네만, 이제 어디로 가야 할지 막막하다네." "우리와 함께 브레멘으로 가세. 자네는 밤 음악에 밝지 않은가. 거기서 거리의 악사가 될 수 있을 걸세." 고양이는 그것이 좋겠다고 여기고 함께 갔습니다. 그러고 나서 세 도망자는 어느 농가 앞을 지나게 되었는데, 대문 위에 수탉이 앉아 온 힘을 다해 울고 있었습니다. "자네 울음소리가 뼛속까지 파고드는군." 하고 당나귀가 말했습니다. "무슨 일인가?" "내가 좋은 날씨를 알렸다네." 하고 수탉이 말했습니다. "오늘은 성모님 날이라, 성모님이 아기 예수의 옷을 빨아 말리시려는 날이지. 그런데 내일 일요일에 손님이 온다고, 안주인은 조금도 봐줄 마음이 없어서 요리사에게 내일 나를 국에 넣어 먹겠다고 했다네. 그래서 나는 오늘 저녁에 목이 잘리게 되었지. 그래서 아직 할 수 있을 때 목청껏 우는 것이라네." "이런, 빨간 머리 친구." 하고 당나귀가 말했습니다. "그러지 말고 우리와 함께 떠나세. 우리는 브레멘으로 가는 길이라네. 죽음보다 나은 것은 어디에서든 찾을 수 있지 않겠나. 자네는 목소리가 좋으니, 우리가 함께 연주하면 제법 그럴듯할 걸세." 수탉은 그 제안이 마음에 들었고, 그리하여 넷은 다 함께 길을 떠났습니다.`,
    source: '그림 형제, 어린이와 가정을 위한 옛이야기 KHM 27 — 이 플랫폼에서 옮김',
  },
]


export const TEST_SENTENCES: TestSentence[] = [
  ...Object.keys(BUILT).flatMap(builtFor),
  ...QUOTED,
  ...TALES,
]

/** The sentences offered for one language, the unloaded ones first. */
export function sentencesFor(language: string): TestSentence[] {
  const order: Record<TestAxis, number> = { neutral: 0, emotional: 1, tale: 2 }
  return TEST_SENTENCES.filter((s) => s.language === language).sort(
    (a, b) => order[a.axis] - order[b.axis]
  )
}
