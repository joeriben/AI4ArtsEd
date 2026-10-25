<!-- The Datenschutz, once: the route /datenschutz (views/DatenschutzView.vue) and the layer
     over the page (components/DatenschutzModal.vue) both render this. The title
     stays with the frame that shows it (legal.privacy.title). -->
<template>
  <p class="privacy-notice">{{ $t('legal.privacy.notice') }}</p>
  <p class="privacy-notice" style="margin-top: 1.5rem;">{{ $t('legal.privacy.usage') }} <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>

  <section>
    <h2>{{ $t('legal.privacy.controller.title') }}</h2>
    <p>
      {{ $t('legal.privacy.controller.content') }}<br>
      E-Mail: <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a>
    </p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.dataProcessing.title') }}</h2>
    <p>{{ $t('legal.privacy.dataProcessing.content') }}</p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.deviceId.title') }}</h2>
    <p>{{ $t('legal.privacy.deviceId.content') }}</p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.uploads.title') }}</h2>
    <p>{{ $t('legal.privacy.uploads.content') }}</p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.cookies.title') }}</h2>
    <p>{{ $t('legal.privacy.cookies.content') }}</p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.externalServices.title') }}</h2>
    <p>{{ $t('legal.privacy.externalServices.content') }}</p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.legalBasis.title') }}</h2>
    <p>{{ $t('legal.privacy.legalBasis.content') }}</p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.retention.title') }}</h2>
    <p>{{ $t('legal.privacy.retention.content') }} <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.rights.title') }}</h2>
    <p>{{ $t('legal.privacy.rights.content') }} <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
  </section>

  <section>
    <h2>{{ $t('legal.privacy.fauReference.title') }}</h2>
    <p>
      {{ $t('legal.privacy.fauReference.content') }}<br>
      <a href="https://www.fau.de/datenschutz" target="_blank" rel="noopener noreferrer">
        www.fau.de/datenschutz
      </a>
    </p>
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

.privacy-notice {
  font-size: 1.1rem;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.9);
  padding: 1.5rem;
  background: rgba(76, 175, 80, 0.1);
  border-left: 3px solid #4CAF50;
  border-radius: 4px;
}
</style>
