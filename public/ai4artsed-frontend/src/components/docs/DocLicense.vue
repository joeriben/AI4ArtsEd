<template>
  <section class="guide-section">
    <h2>{{ t('docs.license.heading') }}</h2>

    <div class="contact-box" style="margin-top: 0; margin-bottom: 1.5rem;">
      <a href="https://github.com/joeriben/ai4artsed/blob/main/LICENSE.md" target="_blank" rel="noopener" class="license-github-link">
        {{ t('docs.license.onGithub') }}
      </a>
      <p style="margin-top: 0.5rem;">UCDCAE AI Lab License v1.1</p>
    </div>

    <!-- GERMAN VERSION -->
    <template v-if="locale === 'de'">
      <h3 class="license-title">Lizenz — AI Lab des UNESCO Chair in Digital Culture and Arts in Education</h3>
      <p class="license-version">Version 1.1 — Oktober 2026</p>
      <p class="license-note"><em>Deutsche Fassung (rechtlich maßgeblich)</em></p>

      <div class="license-section">
        <h4>Präambel</h4>
        <p>Diese Software ist nicht lediglich ein technisches Produkt. Sie ist Ausdruck bildungstheoretischer Forschung im Kontext digitaler Kultureller Bildung und verkörpert wissenschaftliche Erkenntnisse über den pädagogisch verantwortungsvollen Einsatz generativer KI in Bildungskontexten.</p>
        <p>Die Struktur der Software — insbesondere das pädagogische Sicherheitssystem, die Orchestrierungslogik und die Prompt-Interception-Architektur — basiert auf publizierten wissenschaftlichen Überlegungen des Urhebers. Diese Architekturentscheidungen sind nicht beliebig oder austauschbar, sondern bilden die wissenschaftliche Substanz des Werkes.</p>
        <p>Die bildungstheoretischen Grundlagen dieser Software sind u.a. dokumentiert in:</p>
        <ul class="license-refs">
          <li>Jörissen, B. &amp; Baumann, V. (2026). Prompt Interception: Critical (Programming) Practice as Cultural Resilience in the Context of generative Artificial Intelligence. <em>MedienPädagogik</em> (in review).</li>
          <li>Jörissen, B. (2025). AI4ArtsEd-CESEM: A Software Framework for Critical Educational and Scientific Exploration and Manipulation of Generative AI.</li>
          <li>Jörissen, B. (2025). Digitalität im erziehungstheoretischen Blick. In: Fuchs, T. (Hrsg.), <em>Digitalität</em>. Weinheim: Beltz Juventa.</li>
          <li>Jörissen, B., Klepacki, L., Flasche, V. &amp; Zahn, M. (2025). Wahrnehmungskrisen. In: Sturm, T. et al. (Hrsg.), <em>Krisen und Transformationen</em>. Verlag Barbara Budrich, 419–430.</li>
          <li>Jörissen, B. &amp; Klepacki, L. (2025). „Cultural Resilience" and the Cultivation of a Postdigital Planetary Dissensus. In: <em>Becoming Planetary</em> (accepted).</li>
          <li>Jörissen, B. (2022). Digitale Sympoiesis und kulturelle Resilienz. <em>Vierteljahrsschrift für wissenschaftliche Pädagogik</em>, 98(4), 474–489.</li>
        </ul>
        <p>Diese Lizenz dient dem Ziel, die Software der Bildungsgemeinschaft frei zugänglich zu machen und gleichzeitig ihre wissenschaftliche Integrität zu schützen.</p>
      </div>

      <div class="license-section">
        <h4>§1 — Definitionen</h4>
        <p><strong>„Software"</strong> bezeichnet den gesamten Quellcode, die Konfigurationsdateien, Schemata, Dokumentation und zugehörigen Materialien des AI Lab des UNESCO Chair in Digital Culture and Arts in Education.</p>
        <p><strong>„Urheber"</strong> bezeichnet den ursprünglichen Autor der Software, Prof. Dr. Benjamin Jörissen, Friedrich-Alexander-Universität Erlangen-Nürnberg.</p>
        <p><strong>„Nicht-kommerzielle Bildungseinrichtung"</strong> bezeichnet öffentliche und gemeinnützige Institutionen, deren Hauptzweck Bildung, Forschung oder kulturelle Vermittlung ist.</p>
        <p><strong>„Kommerzielle Nutzung"</strong> bezeichnet jeden Einsatz der Software durch oder zugunsten gewinnorientierter Unternehmen oder zu gewinnorientierten Zwecken.</p>
        <p><strong>„Autorisierte Modifikation"</strong> bezeichnet eine Veränderung der Software, für die der Urheber eine schriftliche Genehmigung erteilt hat oder die unter einem gültigen Contributor License Agreement (CLA) erfolgt.</p>
      </div>

      <div class="license-section">
        <h4>§2 — Gewährte Rechte</h4>
        <p>Unter den Bedingungen dieser Lizenz gewährt der Urheber ein unentgeltliches, nicht-exklusives, nicht-übertragbares Recht zu:</p>
        <p><strong>(a) Download und Studium:</strong> Jede natürliche oder juristische Person darf die Software herunterladen und den Quellcode studieren.</p>
        <p><strong>(b) Nutzung zu nicht-kommerziellen Bildungszwecken:</strong> Nicht-kommerzielle Bildungseinrichtungen dürfen die Software installieren, konfigurieren und in ihren Bildungsangeboten einsetzen.</p>
        <p><strong>(c) Nutzung zu nicht-kommerziellen wissenschaftlichen Zwecken:</strong> Jede Person darf die Software in wissenschaftlichen Publikationen referenzieren, zitieren und Auszüge zu Illustrationszwecken verwenden und zu Forschungszwecken installieren, konfigurieren und einsetzen.</p>
      </div>

      <div class="license-section">
        <h4>§3 — Einschränkungen</h4>
        <p><strong>(a) Keine Modifikation ohne Autorisierung:</strong> Die Software darf nicht verändert, angepasst, erweitert oder in abgeleiteter Form erstellt werden, es sei denn, der Urheber hat dies schriftlich genehmigt oder die Modifikation erfolgt unter einem gültigen CLA (siehe §5).</p>
        <p><strong>(b) Keine Redistribution ohne Autorisierung:</strong> Die Software darf nicht weiterverbreitet, veröffentlicht, gespiegelt oder auf andere Weise Dritten zugänglich gemacht werden, es sei denn, der Urheber hat dies schriftlich genehmigt. Hiervon ausgenommen ist die interne Bereitstellung innerhalb einer einzelnen nicht-kommerziellen Bildungseinrichtung.</p>
        <p><strong>(c) Kommerzielle Nutzung nur nach Vereinbarung:</strong> Kommerzielle Nutzung bedarf einer gesonderten schriftlichen Vereinbarung mit dem Urheber.</p>
        <p><strong>(d) Namensnennung:</strong> Bei jeder Nutzung ist der Urheber und die Bezeichnung „AI Lab des UNESCO Chair in Digital Culture and Arts in Education" in angemessener Form zu nennen.</p>
        <p><strong>(e) Pädagogisches Sicherheitssystem und Forschungsmodus:</strong> Die Software enthält ein mehrstufiges Sicherheitssystem zum Schutz von Lernenden. Der Forschungsmodus deaktiviert sämtliche Sicherheitsmechanismen und darf ausschließlich von anerkannten Forschungseinrichtungen zu dokumentierten wissenschaftlichen Zwecken aktiviert werden. Ungefilterte Ausgaben dürfen niemals Minderjährigen oder Lernenden präsentiert werden. Wer den Forschungsmodus außerhalb der Forschung verwendet, verletzt die Lizenz, verliert das unentgeltliche Nutzungsrecht und hat mit einer erheblichen Nutzungsgebührenforderung zu rechnen, zusätzlich zu weiteren rechtlichen Konsequenzen.</p>
      </div>

      <div class="license-section">
        <h4>§4 — Schutz der wissenschaftlichen Integrität</h4>
        <p>Unbefugte Veränderungen, die die pädagogischen Schutzmechanismen, die Orchestrierungslogik oder die bildungstheoretischen Grundprinzipien der Software beeinträchtigen, stellen eine Beeinträchtigung des Werkes im Sinne von §14 UrhG (Entstellungsverbot) dar.</p>
      </div>

      <div class="license-section">
        <h4>§5 — Autorisierung von Modifikationen</h4>
        <p><strong>(a)</strong> Der Urheber kann auf Anfrage schriftliche Genehmigungen für spezifische Modifikationen erteilen.</p>
        <p><strong>(b)</strong> Für regelmäßige Mitwirkende kann der Urheber ein Contributor License Agreement anbieten.</p>
      </div>

      <div class="license-section">
        <h4>§6 — Gewährleistungsausschluss</h4>
        <p>DIE SOFTWARE WIRD „WIE BESEHEN" (AS IS) OHNE JEDE AUSDRÜCKLICHE ODER STILLSCHWEIGENDE GEWÄHRLEISTUNG ZUR VERFÜGUNG GESTELLT.</p>
      </div>

      <div class="license-section">
        <h4>§7 — Beendigung</h4>
        <p>Die durch diese Lizenz gewährten Rechte erlöschen automatisch bei jedem Verstoß gegen die Lizenzbedingungen.</p>
      </div>

      <div class="license-section">
        <h4>§8 — Anwendbares Recht und Gerichtsstand</h4>
        <p>Diese Lizenz unterliegt dem Recht der Bundesrepublik Deutschland. Gerichtsstand ist Erlangen.</p>
      </div>

      <div class="license-section">
        <h4>§9 — Salvatorische Klausel</h4>
        <p>Sollte eine Bestimmung dieser Lizenz unwirksam oder undurchsetzbar sein, bleiben die übrigen Bestimmungen hiervon unberührt.</p>
      </div>

      <div class="license-section">
        <h4>§10 — Kontakt</h4>
        <p>Anfragen zu Genehmigungen, kommerziellen Vereinbarungen und Contributor License Agreements sind zu richten an:</p>
        <p>Prof. Dr. Benjamin Jörissen<br>UNESCO Chair in Digital Culture and Arts in Education<br>Friedrich-Alexander-Universität Erlangen-Nürnberg<br>Bismarckstr. 1a, 91054 Erlangen<br>E-Mail: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a></p>
      </div>
    </template>

    <!-- ENGLISH VERSION -->
    <template v-else>
      <h3 class="license-title">License — AI Lab of the UNESCO Chair in Digital Culture and Arts in Education</h3>
      <p class="license-version">Version 1.1 — October 2026</p>
      <p class="license-note"><em>English translation (for reference only — the German version is legally binding)</em></p>

      <div class="license-section">
        <h4>Preamble</h4>
        <p>This software is not merely a technical product. It is an expression of educational-theoretical research in the context of digital arts and cultural education, embodying scientific insights regarding the pedagogically responsible use of generative AI in educational settings.</p>
        <p>The structure of the software — in particular, its pedagogical safety system, orchestration logic, and prompt interception architecture — is grounded in the author's published academic work. These architectural decisions are neither arbitrary nor interchangeable; they constitute the scientific substance of this work.</p>
        <p>The educational-theoretical foundations of this software are documented in, among others:</p>
        <ul class="license-refs">
          <li>Jörissen, B. &amp; Baumann, V. (2026). Prompt Interception: Critical (Programming) Practice as Cultural Resilience in the Context of generative Artificial Intelligence. <em>MedienPädagogik</em> (in review).</li>
          <li>Jörissen, B. (2025). AI4ArtsEd-CESEM: A Software Framework for Critical Educational and Scientific Exploration and Manipulation of Generative AI.</li>
          <li>Jörissen, B. (2025). Digitalität im erziehungstheoretischen Blick. In: Fuchs, T. (Ed.), <em>Digitalität</em>. Weinheim: Beltz Juventa.</li>
          <li>Jörissen, B., Klepacki, L., Flasche, V. &amp; Zahn, M. (2025). Wahrnehmungskrisen. In: Sturm, T. et al. (Eds.), <em>Krisen und Transformationen</em>. Verlag Barbara Budrich, 419–430.</li>
          <li>Jörissen, B. &amp; Klepacki, L. (2025). "Cultural Resilience" and the Cultivation of a Postdigital Planetary Dissensus. In: <em>Becoming Planetary</em> (accepted).</li>
          <li>Jörissen, B. (2022). Digitale Sympoiesis und kulturelle Resilienz. <em>Vierteljahrsschrift für wissenschaftliche Pädagogik</em>, 98(4), 474–489.</li>
        </ul>
        <p>This license aims to make the software freely available to the educational community while protecting its scientific integrity.</p>
      </div>

      <div class="license-section">
        <h4>Section 1 — Definitions</h4>
        <p><strong>"Software"</strong> means the complete source code, configuration files, schemas, documentation, and associated materials of the AI Lab of the UNESCO Chair in Digital Culture and Arts in Education.</p>
        <p><strong>"Author"</strong> means the original creator of the software, Prof. Dr. Benjamin Jörissen, Friedrich-Alexander-Universität Erlangen-Nürnberg.</p>
        <p><strong>"Non-commercial educational institution"</strong> means public and non-profit institutions whose primary purpose is education, research, or cultural mediation.</p>
        <p><strong>"Commercial use"</strong> means any use of the software by or for the benefit of for-profit enterprises or for profit-oriented purposes.</p>
        <p><strong>"Authorized modification"</strong> means a change to the software for which the author has granted written permission, or which is made under a valid Contributor License Agreement (CLA).</p>
      </div>

      <div class="license-section">
        <h4>Section 2 — Rights Granted</h4>
        <p>Subject to the terms of this license, the author grants a royalty-free, non-exclusive, non-transferable right to:</p>
        <p><strong>(a) Download and study:</strong> Any natural or legal person may download the software and study its source code.</p>
        <p><strong>(b) Non-commercial educational use:</strong> Non-commercial educational institutions may install, configure, and use the software in their educational offerings.</p>
        <p><strong>(c) Academic reference:</strong> Any person may reference and cite the software in academic publications, use excerpts for purposes of illustration, and install, configure, and use the software for research purposes.</p>
      </div>

      <div class="license-section">
        <h4>Section 3 — Restrictions</h4>
        <p><strong>(a) No modification without authorization:</strong> The software may not be modified, adapted, extended, or used to create derivative works unless the author has granted written permission or the modification is made under a valid CLA (see Section 5).</p>
        <p><strong>(b) No redistribution without authorization:</strong> The software may not be redistributed, published, mirrored, or otherwise made available to third parties unless the author has granted written permission. Excepted is internal provision within a single non-commercial educational institution.</p>
        <p><strong>(c) Commercial use only by agreement:</strong> Commercial use requires a separate written agreement with the author.</p>
        <p><strong>(d) Attribution:</strong> Any use must credit the author and include the designation "AI Lab of the UNESCO Chair in Digital Culture and Arts in Education" in an appropriate manner.</p>
        <p><strong>(e) Pedagogical Safety System and Research Mode:</strong> The software contains a multi-stage safety system to protect learners. Research Mode disables all safety mechanisms and may only be activated by recognized research institutions for documented scientific purposes. Unfiltered outputs must never be presented to minors or learners. Anyone who uses Research Mode outside research breaches the license, loses the royalty-free right of use and must expect a substantial claim for usage fees, in addition to further legal consequences.</p>
      </div>

      <div class="license-section">
        <h4>Section 4 — Protection of Scientific Integrity</h4>
        <p>Unauthorized modifications that impair, distort, or remove the pedagogical safety mechanisms, orchestration logic, or fundamental educational-theoretical principles constitute an impairment of the work within the meaning of §14 UrhG (German Copyright Act — prohibition of distortion).</p>
      </div>

      <div class="license-section">
        <h4>Section 5 — Authorization of Modifications</h4>
        <p><strong>(a)</strong> The author may, upon request, grant written permission for specific modifications.</p>
        <p><strong>(b)</strong> For regular contributors, the author may offer a Contributor License Agreement.</p>
      </div>

      <div class="license-section">
        <h4>Section 6 — Disclaimer of Warranty</h4>
        <p>THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY EXPRESS OR IMPLIED WARRANTY.</p>
      </div>

      <div class="license-section">
        <h4>Section 7 — Termination</h4>
        <p>The rights granted under this license terminate automatically upon any breach of the license terms.</p>
      </div>

      <div class="license-section">
        <h4>Section 8 — Governing Law and Jurisdiction</h4>
        <p>This license is governed by the laws of the Federal Republic of Germany. The place of jurisdiction is Erlangen.</p>
      </div>

      <div class="license-section">
        <h4>Section 9 — Severability</h4>
        <p>If any provision of this license is found to be invalid or unenforceable, the remaining provisions shall remain in full force and effect.</p>
      </div>

      <div class="license-section">
        <h4>Section 10 — Contact</h4>
        <p>Requests for permissions, commercial agreements, and Contributor License Agreements shall be directed to:</p>
        <p>Prof. Dr. Benjamin Jörissen<br>UNESCO Chair in Digital Culture and Arts in Education<br>Friedrich-Alexander-Universität Erlangen-Nürnberg<br>Bismarckstr. 1a, 91054 Erlangen<br>Email: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a></p>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t, locale } = useI18n()
</script>

<style scoped>
.license-title {
  color: #ffffff;
  font-size: 1.2rem;
  margin: 0 0 0.5rem 0;
}

.license-version {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  margin: 0 0 0.25rem 0;
}

.license-note {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  margin: 0 0 1.5rem 0;
}

.license-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.license-section:last-of-type {
  border-bottom: none;
}

.license-section h4 {
  color: #4CAF50;
  font-size: 1rem;
  margin: 0 0 0.75rem 0;
}

.license-section p {
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.7;
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
}

.license-section a {
  color: #4CAF50;
  text-decoration: none;
}

.license-section a:hover {
  text-decoration: underline;
}

.license-refs {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
}

.license-refs li {
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.license-github-link {
  display: inline-block;
  padding: 0.5rem 1rem;
  background: rgba(76, 175, 80, 0.2);
  border: 1px solid #4CAF50;
  border-radius: 6px;
  color: #4CAF50 !important;
  font-weight: 700;
  text-decoration: none !important;
  transition: all 0.2s ease;
}

.license-github-link:hover {
  background: rgba(76, 175, 80, 0.3);
}
</style>
