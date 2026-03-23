<template>
  <div class="about-page">
    <div class="about-container">
      <h1>{{ $t('about.title') }}</h1>

      <section class="intro">
        <p>{{ $t('about.intro') }}</p>
      </section>

      <section>
        <h2>{{ $t('about.project.title') }}</h2>
        <p>{{ $t('about.project.description') }}</p>
        <p>{{ $t('about.project.paragraph2') }}</p>
        <p>{{ $t('about.project.paragraph3') }}</p>
        <p>{{ $t('about.project.paragraph4') }}</p>
        <p>
          {{ $t('about.project.moreInfo') }}
          <a href="https://kubi-meta.de/ai4artsed" target="_blank" rel="noopener noreferrer">
            kubi-meta.de/ai4artsed
          </a>
        </p>
      </section>

      <section>
        <h2>{{ $t('about.subproject.title') }}</h2>
        <p>{{ $t('about.subproject.description') }}</p>
      </section>

      <section>
        <h2>{{ $t('about.team.title') }}</h2>
        <div class="team-member">
          <h3>{{ $t('about.team.projectLead') }}</h3>
          <p><strong>{{ $t('about.team.leadName') }}</strong></p>
          <p>{{ $t('about.team.leadInstitute') }}<br>
          {{ $t('about.team.leadChair') }}<br>
          {{ $t('about.team.leadUnesco') }}</p>
          <p>E-Mail: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a></p>
        </div>
        <div class="team-member">
          <h3>{{ $t('about.team.researcher') }}</h3>
          <p><strong>{{ $t('about.team.researcherName') }}</strong></p>
          <p>{{ $t('about.team.researcherInstitute') }}<br>
          {{ $t('about.team.researcherChair') }}<br>
          {{ $t('about.team.researcherUnesco') }}</p>
          <p>E-Mail: <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
        </div>
      </section>

      <section>
        <h2>{{ $t('about.credits.title') }}</h2>
        <ul class="credits-list">
          <li>{{ $t('about.credits.emt140') }}</li>
        </ul>
      </section>

      <section class="funding">
        <h2>{{ $t('about.funding.title') }}</h2>
        <div class="funding-logo">
          <a href="https://www.bmfsfj.de/" target="_blank" rel="noopener noreferrer">
            <img src="/logos/BMBFSFJ_logo.png" alt="BMBFSFJ" />
          </a>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.about-page {
  min-height: 100vh;
  background: #0a0a0a;
  padding: 2rem;
  color: #ffffff;
}

.about-container {
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
  font-weight: 600;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  color: rgba(255, 255, 255, 0.9);
}

section {
  margin-bottom: 1.5rem;
}

p, li {
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.8);
}

ul {
  margin: 1rem 0;
  padding-left: 1.5rem;
}

li {
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

.team-member {
  margin-top: 2rem;
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}

.team-member h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #4CAF50;
  margin-bottom: 0.5rem;
}

.team-member:first-of-type {
  margin-top: 1rem;
}

.funding {
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
  .about-page {
    padding: 1rem;
  }

  .about-container {
    padding: 1.5rem;
  }

  h1 {
    font-size: 1.5rem;
  }
}
</style>
