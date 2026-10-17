<!-- The Impressum, once: the route /impressum (views/ImpressumView.vue) and the layer
     over the page (components/ImpressumModal.vue) both render this. The title
     stays with the frame that shows it (legal.impressum.title). -->
<template>
  <section>
    <h2>{{ $t('legal.impressum.publisher') }}</h2>
    <p>
      Friedrich-Alexander-Universität Erlangen-Nürnberg<br>
      {{ $t('legal.impressum.represented') }} Prof. Dr. Joachim Hornegger<br>
      Freyeslebenstraße 1, 91058 Erlangen<br>
      E-Mail: <a href="mailto:poststelle@fau.de">poststelle@fau.de</a>
    </p>
  </section>

  <section>
    <h2>{{ $t('legal.impressum.responsible') }}</h2>
    <p>
      Prof. Dr. Benjamin Jörissen<br>
      Bismarckstraße 1a, 91054 Erlangen<br>
      E-Mail: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a>
    </p>
  </section>

  <section>
    <h2>{{ $t('legal.impressum.authority') }}</h2>
    <p>
      Bayerisches Staatsministerium für Wissenschaft und Kunst<br>
      Salvatorstraße 2, 80327 München<br>
      <a href="https://www.stmwk.bayern.de/" target="_blank" rel="noopener noreferrer">
        www.stmwk.bayern.de
      </a>
    </p>
  </section>

  <section>
    <h2>{{ $t('legal.impressum.moreInfo') }}</h2>
    <p>
      {{ $t('legal.impressum.moreInfoText') }}<br>
      <a href="https://www.fau.de/impressum" target="_blank" rel="noopener noreferrer">
        www.fau.de/impressum
      </a>
    </p>
  </section>

  <section class="funding-section">
    <h2>{{ $t('legal.impressum.funding') }}</h2>
    <div class="funding-logo">
      <a href="https://www.bmfsfj.de/" target="_blank" rel="noopener noreferrer">
        <img src="/logos/BMBFSFJ_logo.png" alt="BMBFSFJ" />
      </a>
    </div>
  </section>
</template>

<style scoped>
h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  color: rgba(255, 255, 255, 0.9);
}

section {
  margin-bottom: 1.5rem;
}

section:first-child h2 {
  margin-top: 0;
}

p {
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.8);
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

.funding-section {
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.funding-logo {
  margin-top: 1rem;
  text-align: center;
}

.funding-logo img {
  max-width: 400px;
  width: 100%;
  height: auto;
  background: white;
  padding: 1rem;
  border-radius: 8px;
}

@media (max-width: 768px) {
  .funding-logo img {
    max-width: 100%;
  }
}
</style>
