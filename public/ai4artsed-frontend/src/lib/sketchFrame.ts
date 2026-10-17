/**
 * The document a generated sketch runs in.
 *
 * One builder, two consumers (Rule #13 — the frame is not written twice): the
 * sandbox the learner reads, edits and runs in, and the hidden frame that takes
 * the one still picture a board card shows. `captureId` is the whole difference
 * between them — given one, the frame hands a single PNG back up to the page
 * that built it and is then thrown away.
 */

/**
 * A payload that contains the characters ending a script element would close it
 * early, and everything after would be parsed as markup instead of run. The
 * builders escape their own terminators; this escapes the machine's.
 */
export function forFrame(code: string): string {
  return code.replace(/<\/(script)/gi, '<\\/$1')
}

/** Text going into the frame's markup, not into its script. */
export function forFrameText(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** What a captured frame calls itself when it posts its picture up. */
export const SKETCH_FRAME_MESSAGE = 'sketchFrame'

/**
 * When the picture is offered, in milliseconds. Several moments, not one: p5
 * itself is fetched from a CDN, so an early canvas is often still empty, and a
 * sketch that builds its scene needs longer again. The page takes the first
 * offer that has something on it and stops listening.
 */
const CAPTURE_AT_MS = [900, 1800, 3000, 4500, 6500]

/**
 * The still picture, handed to the page that built the frame. It runs inside
 * the sandbox, so the only thing it can reach is `parent.postMessage` — and the
 * only thing it sends is a data URL. A canvas that cannot be read (a sketch
 * that loaded a picture from elsewhere taints it) yields nothing, and nothing
 * depends on the picture arriving.
 */
function captureScript(captureId: string): string {
  return `    <script>
        [${CAPTURE_AT_MS.join(', ')}].forEach(function (ms) {
            setTimeout(function () {
                try {
                    var c = document.querySelector('canvas');
                    if (!c) return;
                    // p5 drives draw() from requestAnimationFrame, and a frame
                    // nobody is looking at never gets one: setup() runs, the
                    // canvas exists, and it stays black for as long as it
                    // lives. Ask for the frames outright.
                    if (typeof redraw === 'function' && typeof frameCount !== 'undefined' && frameCount < 24) {
                        redraw(24 - frameCount);
                    }
                    parent.postMessage(
                        { kind: ${JSON.stringify(SKETCH_FRAME_MESSAGE)}, id: ${JSON.stringify(captureId)}, png: c.toDataURL('image/png') },
                        '*'
                    );
                } catch (e) {}
            }, ms);
        });
    <\/script>
`
}

export function p5jsFrame(code: string, captureId = ''): string {
  const codeToRender = forFrame(code)
  if (!codeToRender) return ''

  return `<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: #f7fafc;
        }
        canvas {
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .error-display {
            color: #ff6b6b;
            padding: 20px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            white-space: pre-wrap;
            max-width: 90%;
            text-align: left;
        }
    </style>
    <script>
        window.onerror = function(msg, url, line, col, error) {
            document.body.innerHTML = '<div class="error-display">Error (line ' + line + '): ' + msg + '<\\/div>';
            return true;
        };
    <\/script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.7.0/p5.min.js"><\/script>
</head>
<body>
    <script>
        ${codeToRender}
    <\/script>
${captureId ? captureScript(captureId) : ''}</body>
</html>`
}
