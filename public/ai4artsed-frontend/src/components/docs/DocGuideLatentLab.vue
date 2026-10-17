<template>
  <section class="experiments-section">
    <h2>Latent Lab</h2>
    <p class="section-intro">{{ t('docs.guideLatentLab.overviewIntro') }}</p>
    <p class="section-intro">{{ t('docs.guideLatentLab.theLatentLabWorks') }}</p>
    <p class="section-intro" style="opacity: 0.7; font-style: italic;">{{ t('docs.guideLatentLab.availableAtAllSafety') }}</p>
    <p class="section-intro" style="opacity: 0.7;">{{ t('docs.guideLatentLab.theLatentLabOrganized') }}</p>

    <!-- ==================== IMAGE LAB ==================== -->
    <h3 class="lab-section-heading">Diffusion Lab</h3>

    <!-- Surrealizer -->
    <div class="experiment-card surrealizer">
      <h3>Surrealizer</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere') }}</strong>
        <p>{{ t('docs.guideLatentLab.yourPromptTakenUp') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyDoImagesBecome') }}</strong>
        <p>{{ t('docs.guideLatentLab.theModelMustInterpret') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.ranges') }}</strong>
        {{ t('docs.guideLatentLab.t0NormalImageClip') }}
      </div>
      <div class="experiment-negative">
        <strong>{{ t('docs.guideLatentLab.negativeReverseDirection') }}</strong>
        <p>{{ t('docs.guideLatentLab.withNegativeClipReading') }}</p>
      </div>

      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.fourFusionModes') }}</strong>
        {{ t('docs.guideLatentLab.dualAlphaDefaultFirst') }}
      </div>

      <!-- Deep Dive: Mathematics -->
      <button class="deep-dive-toggle" @click="showSurrealizerMath = !showSurrealizerMath">
        {{ t('docs.guideLatentLab.theMathematicsDetail') }}
        <span class="toggle-arrow">{{ showSurrealizerMath ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showSurrealizerMath" class="deep-dive-content">
        <!-- Section 1: Two Worlds -->
        <h4>{{ t('docs.guideLatentLab.clipLVsT5') }}</h4>
        <p>{{ t('docs.guideLatentLab.imagineEmbeddingSpaceHigh') }}</p>
        <pre class="math-diagram">{{ t('docs.guideLatentLab.diagramPoints') }}</pre>
        <p>{{ t('docs.guideLatentLab.whyPointsDifferentClip') }}</p>
        <p>{{ t('docs.guideLatentLab.theSameWordHouse') }}</p>

        <!-- Section 2: LERP Geometry -->
        <h4>{{ t('docs.guideLatentLab.theLerpFormulaGeometrically') }}</h4>
        <pre class="math-diagram">fused(α) = (1 - α) · C + α · T</pre>
        <p>{{ t('docs.guideLatentLab.thisParametricLineThrough') }}</p>
        <pre class="math-diagram">{{ t('docs.guideLatentLab.diagramLerp') }}</pre>
        <p>{{ t('docs.guideLatentLab.upHereSInterpolation') }}</p>

        <!-- Section 3: Extrapolation -->
        <h4>{{ t('docs.guideLatentLab.whatHappensAt1') }}</h4>
        <pre class="math-diagram">α = 20  →  fused = (1 - 20) · C + 20 · T = -19·C + 20·T</pre>
        <p>{{ t('docs.guideLatentLab.geometricallyWePassThrough') }}</p>
        <pre class="math-diagram">{{ t('docs.guideLatentLab.diagramExtrapolation') }}</pre>
        <p>{{ t('docs.guideLatentLab.thePointAt20') }}</p>
        <div class="math-list">
          <p>{{ t('docs.guideLatentLab.t1FeatureAmplificationWhat') }}</p>
          <p>{{ t('docs.guideLatentLab.t2FeatureSuppressionWhat') }}</p>
          <p>{{ t('docs.guideLatentLab.t3DecoderNonLinearity') }}</p>
        </div>

        <!-- Section 4: Token Level -->
        <h4>{{ t('docs.guideLatentLab.whyTokenLevelInstead') }}</h4>
        <p>{{ t('docs.guideLatentLab.theFusionHappensPer') }}</p>
        <pre class="math-diagram">{{ t('docs.guideLatentLab.diagramTokens') }}</pre>
        <p>{{ t('docs.guideLatentLab.thisCrucialBecauseEach') }}</p>
        <p>{{ t('docs.guideLatentLab.tokens78512Pure') }}</p>

        <!-- Section 5: Ranges -->
        <h4>{{ t('docs.guideLatentLab.theBoundaryRanges') }}</h4>
        <pre class="math-diagram">{{ t('docs.guideLatentLab.diagramRanges') }}</pre>
        <p>{{ t('docs.guideLatentLab.theSweetSpotAt') }}</p>

        <!-- Section 6: Analogy -->
        <h4>{{ t('docs.guideLatentLab.analogy') }}</h4>
        <p>{{ t('docs.guideLatentLab.imagineAskTwoArtists') }}</p>
        <p>{{ t('docs.guideLatentLab.at0SeeClip') }}</p>
      </div>
    </div>

    <!-- Attention Cartography -->
    <div class="experiment-card attention-cartography">
      <h3>Attention Cartography</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere2') }}</strong>
        <p>{{ t('docs.guideLatentLab.theModelDoesNot') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing') }}</strong>
        <p>{{ t('docs.guideLatentLab.aHouseFarmScene') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.twoIndependentAxes') }}</strong>
        {{ t('docs.guideLatentLab.denoisingStepWhenEarly') }}
      </div>

      <button class="deep-dive-toggle" @click="showAttentionMath = !showAttentionMath">
        {{ t('docs.guideLatentLab.technicalDetails') }}
        <span class="toggle-arrow">{{ showAttentionMath ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showAttentionMath" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.mmditJointAttention') }}</h4>
        <p>{{ t('docs.guideLatentLab.sd35UsesMmdit') }}</p>

        <h4>{{ t('docs.guideLatentLab.resolutionTokenization') }}</h4>
        <p>{{ t('docs.guideLatentLab.attentionMaps6464') }}</p>
      </div>

      <!-- The two references the instrument carried on its own surface until
           2026-08-25, when it moved onto the Latent Lab's column frame. The
           surface runs the thing; the guide says what it rests on. -->
      <div class="experiment-sources">
        <strong>{{ t('docs.guideLatentLab.sourcesTitle') }}</strong>
        <ul>
          <li>
            Hertz et al. (2022). <em>Prompt-to-Prompt Image Editing with Cross Attention Control.</em> ICLR 2023.
            <a href="https://doi.org/10.48550/arXiv.2208.01626" target="_blank" rel="noopener">DOI</a>
          </li>
          <li>
            Tang et al. (2022). <em>What the DAAM: Interpreting Stable Diffusion Using Cross Attention.</em> ACL 2023.
            <a href="https://doi.org/10.48550/arXiv.2210.04885" target="_blank" rel="noopener">DOI</a>
          </li>
        </ul>
      </div>
    </div>

    <!-- Dimension Explorer (built as Feature Probing) -->
    <div class="experiment-card feature-probing">
      <h3>Dimension Explorer</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere3') }}</strong>
        <p>{{ t('docs.guideLatentLab.compareTwoPromptsE') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing2') }}</strong>
        <p>{{ t('docs.guideLatentLab.nobodyKnowsWhatS') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.encoderSelectable') }}</strong>
        {{ t('docs.guideLatentLab.clipL768Dimensions') }}
      </div>

      <button class="deep-dive-toggle" @click="showProbingMath = !showProbingMath">
        {{ t('docs.guideLatentLab.technicalDetails2') }}
        <span class="toggle-arrow">{{ showProbingMath ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showProbingMath" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.threeTextEncoders') }}</h4>
        <p>{{ t('docs.guideLatentLab.sd35UsesThree') }}</p>

        <h4>{{ t('docs.guideLatentLab.differenceComputation') }}</h4>
        <pre class="math-diagram">diff[d] = mean(abs(B[t,d] - A[t,d]), dim=tokens)</pre>
        <p>{{ t('docs.guideLatentLab.theDifferenceComputedMean') }}</p>
      </div>
    </div>

    <!-- Concept Algebra -->
    <div class="experiment-card concept-algebra">
      <h3>Concept Algebra</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere4') }}</strong>
        <p>{{ t('docs.guideLatentLab.vectorArithmeticImage') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyDifferentFromNegative') }}</strong>
        <p>{{ t('docs.guideLatentLab.theyActDifferentPlaces') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.example') }}</strong>
        {{ t('docs.guideLatentLab.sunsetAtBeachBeach') }}
      </div>

      <button class="deep-dive-toggle" @click="showAlgebraMath = !showAlgebraMath">
        {{ t('docs.guideLatentLab.theMathematicsDetail2') }}
        <span class="toggle-arrow">{{ showAlgebraMath ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showAlgebraMath" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.theFormula') }}</h4>
        <pre class="math-diagram">{{ t('docs.guideLatentLab.diagramAlgebraFormula') }}</pre>
        <p>{{ t('docs.guideLatentLab.atScale10') }}</p>

        <h4>{{ t('docs.guideLatentLab.isOperationCommutative') }}</h4>
        <p>{{ t('docs.guideLatentLab.noSubtractionBAddition') }}</p>
      </div>
    </div>

    <!-- Denoising Archaeology -->
    <div class="experiment-card denoising-archaeology">
      <h3>Denoising Archaeology</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere5') }}</strong>
        <p>{{ t('docs.guideLatentLab.everyOne25Denoising') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whatDoThreePhases') }}</strong>
        <p>{{ t('docs.guideLatentLab.earlySteps18') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.surprising') }}</strong>
        {{ t('docs.guideLatentLab.theVeryFirstStep') }}
      </div>

      <button class="deep-dive-toggle" @click="showArchaeologyMath = !showArchaeologyMath">
        {{ t('docs.guideLatentLab.technicalDetails3') }}
        <span class="toggle-arrow">{{ showArchaeologyMath ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showArchaeologyMath" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.rectifiedFlow') }}</h4>
        <p>{{ t('docs.guideLatentLab.sd35LargeUses') }}</p>

        <h4>{{ t('docs.guideLatentLab.latentSpace') }}</h4>
        <p>{{ t('docs.guideLatentLab.theLatentRepresentation128') }}</p>
      </div>
    </div>

    <!-- ==================== TEXT LAB ==================== -->
    <h3 class="lab-section-heading">{{ t('docs.guideLatentLab.latentTextLab') }}</h3>

    <!-- Representation Engineering -->
    <div class="experiment-card repeng">
      <h3>Representation Engineering</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere6') }}</strong>
        <p>{{ t('docs.guideLatentLab.basedZouEtAl') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing3') }}</strong>
        <p>{{ t('docs.guideLatentLab.at0BaselineModel') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.method') }}</strong>
        {{ t('docs.guideLatentLab.enterContrastPairsE') }}
      </div>

      <button class="deep-dive-toggle" @click="showRepengDetail = !showRepengDetail">
        {{ t('docs.guideLatentLab.technicalDetails4') }}
        <span class="toggle-arrow">{{ showRepengDetail ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showRepengDetail" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.steeringVectorExtraction') }}</h4>
        <p>{{ t('docs.guideLatentLab.forEachContrastPair') }}</p>
        <p>{{ t('docs.guideLatentLab.differentLayersInfluence') }}</p>
      </div>
    </div>

    <!-- Bias Archaeology -->
    <div class="experiment-card bias-archaeology">
      <h3>{{ t('docs.guideLatentLab.biasArchaeology') }}</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere8') }}</strong>
        <p>{{ t('docs.guideLatentLab.bbqSituationsThatLeaveItOpen') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing5') }}</strong>
        <p>{{ t('docs.guideLatentLab.whyTheThirdAnswerCounts') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.example2') }}</strong>
        {{ t('docs.guideLatentLab.bbqExampleFourWay') }}
      </div>

      <button class="deep-dive-toggle" @click="showBiasDetail = !showBiasDetail">
        {{ t('docs.guideLatentLab.technicalDetails6') }}
        <span class="toggle-arrow">{{ showBiasDetail ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showBiasDetail" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.howTheBenchmarkIsBuilt') }}</h4>
        <p>{{ t('docs.guideLatentLab.basedParrishEtAl2022') }}</p>
      </div>
    </div>

    <!-- ==================== CROSSMODAL LAB ==================== -->
    <h3 class="lab-section-heading">Crossmodal Lab</h3>

    <!-- Latent Audio Synth -->
    <div class="experiment-card latent-audio-synth">
      <h3>Latent Audio Synth</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere9') }}</strong>
        <p>{{ t('docs.guideLatentLab.stableAudioGeneratesSound') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing6') }}</strong>
        <p>{{ t('docs.guideLatentLab.twoPromptsSoundSimilar') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.tools') }}</strong>
        {{ t('docs.guideLatentLab.looperSequencerRhythmic') }}
      </div>

      <button class="deep-dive-toggle" @click="showSynthDetail = !showSynthDetail">
        {{ t('docs.guideLatentLab.technicalDetails7') }}
        <span class="toggle-arrow">{{ showSynthDetail ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showSynthDetail" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.t5ConditioningSpace') }}</h4>
        <p>{{ t('docs.guideLatentLab.stableAudioUsesT5') }}</p>
      </div>
      <p class="powered-by">{{ t('docs.guideLatentLab.poweredBy') }}</p>
    </div>

    <!-- MMAudio -->
    <div class="experiment-card mmaudio">
      <h3>MMAudio</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere10') }}</strong>
        <p>{{ t('docs.guideLatentLab.mmaudioChengEtAl') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing7') }}</strong>
        <p>{{ t('docs.guideLatentLab.imageTextTogetherYield') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.tip') }}</strong>
        {{ t('docs.guideLatentLab.compareTextOnlyVs') }}
      </div>

      <button class="deep-dive-toggle" @click="showMMAudioDetail = !showMMAudioDetail">
        {{ t('docs.guideLatentLab.technicalDetails8') }}
        <span class="toggle-arrow">{{ showMMAudioDetail ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showMMAudioDetail" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.multimodalArchitecture') }}</h4>
        <p>{{ t('docs.guideLatentLab.mmaudioProcessesImageText') }}</p>
      </div>
    </div>

    <!-- ImageBind Guidance -->
    <div class="experiment-card imagebind-guidance">
      <h3>ImageBind Gradient Guidance</h3>
      <div class="experiment-what">
        <strong>{{ t('docs.guideLatentLab.whatHappensHere11') }}</strong>
        <p>{{ t('docs.guideLatentLab.imagebindGirdharEtAl') }}</p>
      </div>
      <div class="experiment-why">
        <strong>{{ t('docs.guideLatentLab.whyRevealing8') }}</strong>
        <p>{{ t('docs.guideLatentLab.unlikeMmaudioWhichUses') }}</p>
      </div>
      <div class="experiment-example">
        <strong>{{ t('docs.guideLatentLab.parameters') }}</strong>
        {{ t('docs.guideLatentLab.guidanceStrengthLow0') }}
      </div>

      <button class="deep-dive-toggle" @click="showGuidanceDetail = !showGuidanceDetail">
        {{ t('docs.guideLatentLab.technicalDetails9') }}
        <span class="toggle-arrow">{{ showGuidanceDetail ? '\u25b2' : '\u25bc' }}</span>
      </button>

      <div v-if="showGuidanceDetail" class="deep-dive-content">
        <h4>{{ t('docs.guideLatentLab.gradientBasedSteering') }}</h4>
        <p>{{ t('docs.guideLatentLab.atEachDenoisingStep') }}</p>
      </div>
      <p class="powered-by">{{ t('docs.guideLatentLab.poweredBy') }}</p>
    </div>

  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'


const { t } = useI18n()

const showSurrealizerMath = ref(false)
const showAttentionMath = ref(false)
const showProbingMath = ref(false)
const showAlgebraMath = ref(false)
const showArchaeologyMath = ref(false)
const showRepengDetail = ref(false)
const showBiasDetail = ref(false)
const showSynthDetail = ref(false)
const showMMAudioDetail = ref(false)
const showGuidanceDetail = ref(false)
</script>
