/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// Google model-viewer web component
declare module '@google/model-viewer' {}
declare namespace JSX {
  interface IntrinsicElements {
    'model-viewer': any
  }
}
