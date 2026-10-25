# Third-Party Credits

This file documents third-party assets and code used in the AI4ArtsEd frontend.

## JavaScript Libraries (CDN)

### p5.js

- **Source**: p5.js Foundation
- **Website**: https://p5js.org/
- **CDN**: https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.7.0/p5.min.js
- **License**: LGPL-2.1 (GNU Lesser General Public License v2.1)
- **License URL**: https://github.com/processing/p5.js/blob/main/license.txt
- **Used in**: `src/views/text_transformation.vue` (iframe for generative graphics)
- **Description**: A JavaScript library for creative coding, making coding accessible for artists, designers, educators, and beginners.

### Tone.js

- **Source**: Tone.js by Yotam Mann
- **Website**: https://tonejs.github.io/
- **CDN**: https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js
- **License**: MIT
- **License URL**: https://github.com/Tonejs/Tone.js/blob/dev/LICENSE.md
- **Used in**: `src/views/text_transformation.vue` (iframe for browser-based music synthesis)
- **Description**: A Web Audio framework for creating interactive music in the browser.

## Animations

### Flying Bird Animation (ForestMiniGame.vue)

- **Source**: CodePen by Kome
- **Original**: https://codepen.io/hoangdacviet/pen/GRWvWmg
- **Tutorial**: https://dev.to/hoangdacviet/code-flying-bird-animation-with-css-on-web-app-3oca
- **Asset URL**: https://s3-us-west-2.amazonaws.com/s.cdpn.io/174479/bird-cells.svg
- **License**: MIT (CodePen default)
- **Used in**: `src/components/edutainment/ForestMiniGame.vue`
- **Modifications**:
  - Scaled down to 40%
  - Applied white color filter
  - Flipped direction (scaleX(-1)) for right-to-left movement
