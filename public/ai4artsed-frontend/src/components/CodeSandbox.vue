<template>
  <!-- The listing and the running piece, side by side: what the machine wrote
       can be read, changed and run again without leaving the page. -->
  <div class="code-sandbox" :class="kind">
    <div class="cs-code">
      <div class="cs-head">
        <span class="cs-title">{{ kind === 'p5js' ? 'p5.js' : 'Tone.js' }}</span>
        <button class="cs-run" :title="t('codeSandbox.run')" @click="runCode">
          &#9654;&#160;{{ t('codeSandbox.run') }}
        </button>
      </div>
      <textarea v-model="editedCode" class="cs-text" spellcheck="false"></textarea>
    </div>
    <div class="cs-view">
      <iframe
        :key="iframeKey"
        :srcdoc="kind === 'p5js' ? getP5jsIframeContent() : getToneJsIframeContent()"
        class="cs-frame"
        sandbox="allow-scripts"
      ></iframe>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { forFrame, forFrameText, p5jsFrame } from '@/lib/sketchFrame'

const { t } = useI18n()

const props = defineProps<{
  /** The code as the machine wrote it. */
  code: string
  kind: 'p5js' | 'tonejs'
}>()

/** What is edited here; the machine's version stays readable underneath. */
const editedCode = ref(props.code)
watch(
  () => props.code,
  (c) => {
    editedCode.value = c
  }
)
/**
 * What the frame is currently running. Deliberately NOT `editedCode`: bound
 * straight to the srcdoc, every keystroke would re-navigate the frame, so a
 * sketch would restart continuously and half-typed code would run and throw.
 * Running is a decision, and this ref is where that decision lands.
 */
const runningCode = ref(props.code)
watch(
  () => props.code,
  (c) => {
    runningCode.value = c
  }
)
/** The frame is not asked to reload — it is replaced, which is the only way a
    sandboxed document reliably starts over. */
const iframeKey = ref(0)
function runCode() {
  if (!editedCode.value) return
  runningCode.value = editedCode.value
  iframeKey.value++
}

function getP5jsIframeContent(): string {
  // No capture id: this frame is the one on screen, and nothing is taken
  // from it. The board card's picture comes from a frame nobody sees.
  return p5jsFrame(runningCode.value)
}

function getToneJsIframeContent(): string {
  const codeToRender = forFrame(runningCode.value)
  if (!codeToRender) return ''

  return `<!DOCTYPE html>
<html>
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js"><\/script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .controls {
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
        }
        button {
            padding: 16px 32px;
            font-size: 18px;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 700;
        }
        .play-btn {
            background: linear-gradient(135deg, #FF4081 0%, #FF6EC4 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(255, 64, 129, 0.4);
        }
        .play-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 20px rgba(255, 64, 129, 0.6);
        }
        .play-btn:active {
            transform: scale(0.98);
        }
        .stop-btn {
            background: linear-gradient(135deg, #424242 0%, #616161 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }
        .stop-btn:hover {
            transform: scale(1.05);
        }
        .status {
            font-size: 14px;
            color: #b0b0b0;
            margin-top: 10px;
        }
        .status.playing {
            color: #FF4081;
        }
        .visualizer {
            width: 200px;
            height: 60px;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 4px;
            margin-top: 20px;
        }
        .bar {
            width: 8px;
            background: linear-gradient(180deg, #FF4081 0%, #FF6EC4 100%);
            border-radius: 4px;
            transition: height 0.1s ease;
        }
        .error {
            color: #ff6b6b;
            padding: 20px;
            font-family: monospace;
            background: rgba(255, 107, 107, 0.1);
            border-radius: 8px;
            max-width: 80%;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="controls">
        <button class="play-btn" id="playBtn">${forFrameText(t('codeSandbox.framePlay'))}</button>
        <button class="stop-btn" id="stopBtn">${forFrameText(t('codeSandbox.frameStop'))}</button>
    </div>
    <div class="status" id="status">${forFrameText(t('textTransform.audioPlayerHint'))}</div>
    <div class="visualizer" id="visualizer">
        <div class="bar" style="height: 20px"></div>
        <div class="bar" style="height: 30px"></div>
        <div class="bar" style="height: 25px"></div>
        <div class="bar" style="height: 40px"></div>
        <div class="bar" style="height: 35px"></div>
        <div class="bar" style="height: 28px"></div>
        <div class="bar" style="height: 32px"></div>
    </div>
    <script>
        let isPlaying = false;
        let visualizerInterval = null;
        const bars = document.querySelectorAll('.bar');

        function updateVisualizer() {
            bars.forEach(bar => {
                const height = Math.random() * 50 + 10;
                bar.style.height = height + 'px';
            });
        }

        function startVisualizer() {
            visualizerInterval = setInterval(updateVisualizer, 100);
        }

        function stopVisualizer() {
            clearInterval(visualizerInterval);
            bars.forEach(bar => bar.style.height = '20px');
        }

        document.getElementById('playBtn').onclick = async () => {
            if (isPlaying) return;

            try {
                await Tone.start();
                document.getElementById('status').textContent = ${JSON.stringify('🎵 ' + t('codeSandbox.playing'))};
                document.getElementById('status').classList.add('playing');
                isPlaying = true;
                startVisualizer();

                // Execute generated code
                ${codeToRender}
            } catch (error) {
                document.getElementById('status').textContent = ${JSON.stringify('❌ ' + t('textTransform.audioPlayerError') + ' ')} + error.message;
                console.error('Tone.js error:', error);
            }
        };

        document.getElementById('stopBtn').onclick = () => {
            Tone.Transport.stop();
            Tone.Transport.cancel();

            // Dispose all scheduled events
            Tone.Transport.position = 0;

            document.getElementById('status').textContent = ${JSON.stringify('⏹️ ' + t('codeSandbox.stopped'))};
            document.getElementById('status').classList.remove('playing');
            isPlaying = false;
            stopVisualizer();
        };
    <\/script>
</body>
</html>`
}
</script>

<style scoped>
.code-sandbox {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  width: 100%;
  height: 100%;
  min-height: 0;
}
@media (max-width: 860px) {
  .code-sandbox {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  }
}
.cs-code,
.cs-view {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: var(--bg-base);
  overflow: hidden;
}
.cs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.cs-title {
  font-size: 0.82rem;
  font-weight: 400;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.72);
}
.cs-run {
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.78rem;
  padding: 4px 10px;
  cursor: pointer;
}
.cs-run:hover {
  border-color: rgba(255, 255, 255, 0.45);
}
.cs-text {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  resize: none;
  border: 0;
  outline: none;
  padding: 10px 12px;
  background: transparent;
  color: rgba(255, 255, 255, 0.9);
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
}
.cs-frame {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  border: 0;
  background: var(--bg-base);
}
</style>
