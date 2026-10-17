<template>
  <div class="docs-page">
    <div class="docs-container">
      <h1>{{ $t('docs.title') }}</h1>

      <section>
        <h2>{{ $t('docs.intro.title') }}</h2>
        <p>{{ $t('docs.intro.content') }}</p>
      </section>

      <section>
        <h2>{{ $t('docs.gettingStarted.title') }}</h2>
        <ol>
          <li>{{ $t('docs.gettingStarted.step1') }}</li>
          <li>{{ $t('docs.gettingStarted.step2') }}</li>
          <li>{{ $t('docs.gettingStarted.step3') }}</li>
        </ol>
      </section>

      <section>
        <h2>{{ $t('docs.modes.title') }}</h2>
        <ul>
          <li><strong>{{ $t('docs.modes.mode1.name') }}:</strong> {{ $t('docs.modes.mode1.desc') }}</li>
          <li><strong>{{ $t('docs.modes.mode2.name') }}:</strong> {{ $t('docs.modes.mode2.desc') }}</li>
          <li><strong>{{ $t('docs.modes.mode3.name') }}:</strong> {{ $t('docs.modes.mode3.desc') }}</li>
        </ul>
      </section>

      <section>
        <h2>{{ $t('docs.wikipedia.title') }}</h2>
        <p><em>{{ $t('docs.wikipedia.subtitle') }}</em></p>

        <h3>{{ $t('docs.wikipedia.languages') }}</h3>
        <p>{{ $t('docs.wikipedia.feature') }}</p>
        <p>{{ $t('docs.wikipedia.languagesDesc') }}</p>
        <ul>
          <li>{{ $t('docs.wikipedia.examples.nigeria') }}</li>
          <li>{{ $t('docs.wikipedia.examples.india') }}</li>
          <li>{{ $t('docs.wikipedia.examples.indigenous') }}</li>
        </ul>

        <h3>{{ $t('docs.wikipedia.why') }}</h3>
        <p>{{ $t('docs.wikipedia.whyDesc') }}</p>

        <h3>{{ $t('docs.wikipedia.culturalRespect') }}</h3>
        <p>{{ $t('docs.wikipedia.culturalRespectDesc') }}</p>

        <p><em>{{ $t('docs.wikipedia.limitations') }}</em></p>
      </section>

      <section>
        <h2>{{ $t('docs.support.title') }}</h2>
        <p>
          {{ $t('docs.support.content') }}<br>
          E-Mail: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a>
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.docs-page {
  min-height: 100%;
  background: var(--bg-base);
  padding: 2rem;
  color: #ffffff;
}

.docs-container {
  max-width: 900px;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 2.5rem;
}

h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 2rem;
  color: #ffffff;
  border-bottom: 2px solid rgba(76, 175, 80, 0.3);
  padding-bottom: 0.5rem;
}

h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  color: rgba(255, 255, 255, 0.9);
}

h3 {
  font-size: 1.1rem;
  font-weight: 400;
  margin-top: 1.5rem;
  margin-bottom: 0.5rem;
  color: rgba(255, 255, 255, 0.85);
}

section {
  margin-bottom: 1.5rem;
}

p, li {
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.8);
}

em {
  color: rgba(255, 255, 255, 0.7);
  font-style: italic;
}

ol, ul {
  margin: 1rem 0;
  padding-left: 2rem;
}

ol li, ul li {
  margin-bottom: 0.75rem;
}

a {
  color: #4CAF50;
  text-decoration: none;
  transition: color 0.3s ease;
}

a:hover {
  color: #66BB6A;
  text-decoration: underline;
}

@media (max-width: 768px) {
  .docs-page {
    padding: 1rem;
  }

  .docs-container {
    padding: 1.5rem;
  }

  h1 {
    font-size: 1.5rem;
  }
}
</style>
