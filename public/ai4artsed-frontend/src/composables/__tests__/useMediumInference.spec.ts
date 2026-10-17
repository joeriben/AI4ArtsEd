/**
 * A catchword counts where it begins a word, and a few medium words also where
 * they close one (2026-09-27). A Prompt Interception text about gouache "auf
 * festem Karton" had lit the sound glyph through the 'ton' inside "Karton", and
 * the flow generated audio for a picture. Whole words alone would have lost
 * every inflected form and every compound; both are held here.
 */
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useMediumInference } from '../useMediumInference'

function read(text: string) {
  const { media, primary } = useMediumInference(ref(text))
  return { media: [...media.value].sort(), primary: primary.value }
}

// The whole text the flow read on 2026-09-27, as the Prompt Interception wrote it.
const BAUHAUS =
  'Gouache und schwarze Tusche auf festem Karton, quadratisches Format. Im Bildzentrum ' +
  'steht ein Kubus aus Beton und Stahl: ein Wohn- und Arbeitshaus mit Flachdach. Die ' +
  'Fassade ist als Raster vertikaler Stützen und liegender Glasbänder organisiert, die ' +
  'Tür ein quadratisches Feld in Gelb, jedes Fenster ein Rechteck, dessen Größe der ' +
  'inneren Nutzung entspricht – Licht, Belüftung, Erschließung. Um den Kubus liegt die ' +
  'Landschaft als flächige Komposition: landwirtschaftliche Nutzflächen erscheinen als ' +
  'streng geteilte Rechtecke in Blau, Gelb und Grau, Feldraine als gerade schwarze ' +
  'Linien, ein Weg als weißes Band, das Haus und Horizont verbindet. Die Natur ist auf ' +
  'Grundformen reduziert: Bäume als Kreise auf senkrechten Linien, ein Hügel als ' +
  'flaches Dreieck, Wasser als horizontale graue Ebene. Die Tiere sind als ' +
  'Nutzeinheiten gebaut: eine Kuh als liegender Quader mit vier Zylindern als Beinen ' +
  'und einem Kreis als Kopf, Hühner als kleine Kugeln mit Dreiecksschnäbeln, ein Hund ' +
  'als Rechteck in Bewegung; jede Silhouette folgt der Funktion Milch, Eier, ' +
  'Wachsamkeit. Die Menschen sind proportionierte Figuren aus Kugel, Zylinder und ' +
  'Quader: Kopf als Kreis, Rumpf als Rechteck, Gliedmaßen als gerade Linien. Ein Bauer ' +
  'trägt eine gelbe Fläche, eine Frau eine blaue, ein Kind einen roten Kreis; ihre ' +
  'Tätigkeiten – Gehen, Tragen, Stehen – sind über Konstruktionsachsen und Pfeile ' +
  'festgelegt. Der Boden ist ein weißes Band, der Himmel eine flache graue Ebene mit ' +
  'einer gelben Kreisscheibe, deren Position die Schatten der Figuren als schwarze ' +
  'Parallelogramme definiert. Warme Farben liegen vorn am Haus, kalte hinten in der ' +
  'Ebene, Schwarz nur als Linie und Schatten. Jede Form hat eine messbare Größe, jede ' +
  'Farbe eine feste Position im Raster, jede Figur eine Aufgabe im Gesamtablauf.'

describe('medium inference', () => {
  it('reads the whole Bauhaus text as a picture', () => {
    const r = read(BAUHAUS)
    expect(r.primary).toBe('image')
    expect(r.media).not.toContain('sound')
  })

  it('does not find a catchword inside or at the end of another word', () => {
    for (const text of [
      'Karton', 'Beton', 'a stone wall', 'cotton', 'Gliedmaßen', 'warme Farbtöne',
      'im Einklang', 'eine Straßenszene', 'die Kunstbewegung', 'Distanz', 'emotion',
    ]) {
      expect(read(text).media, text).toEqual([])
    }
  })

  it('keeps the inflected forms of a catchword', () => {
    for (const text of [
      'tanzende Roboter', 'die Kinder tanzen im Regen', 'ein fliegender Drache',
      'ein laufender Hund im Park', 'ein bewegtes Bild',
    ]) {
      expect(read(text).primary, text).toBe('video')
    }
  })

  it('reads a compound by the medium it opens with or closes with', () => {
    const cases: Array<[string, string]> = [
      ['Komponiere ein Musikstück über den Regen', 'sound'],
      ['Tonaufnahme vom Meer', 'sound'],
      ['Liedtext über den Sommer', 'sound'],
      ['Create a soundtrack for a rainy day', 'sound'],
      ['Rockmusik über eine Katze', 'sound'],
      ['Hintergrundmusik für ein Computerspiel', 'sound'],
      ['ein Kinderlied', 'sound'],
      ['ein Musikvideo mit tanzenden Robotern', 'sound'],
      ['ein Trickfilm über einen Hund', 'video'],
      ['ein Kurzfilm über Freundschaft', 'video'],
      ['Videospiel', 'video'],
      ['Filmmusik für einen Western', 'video'],
      ['Tanzmusik', 'video'],
      ['ein Ölgemälde', 'image'],
      ['eine Holzskulptur', '3d'],
    ]
    for (const [text, medium] of cases) expect(read(text).primary, text).toBe(medium)
  })

  it('finds singular and plural', () => {
    expect(read('ein Lied').primary).toBe('sound')
    expect(read('drei Lieder').primary).toBe('sound')
    expect(read('Klänge im Wald').primary).toBe('sound')
    expect(read('Skulpturen aus Holz').media).toContain('3d')
  })

  it('takes a hyphen and a full stop as a boundary', () => {
    expect(read('ein Musik-Stück').media).toContain('sound')
    expect(read('ein Sketch in p5.js').media).toContain('code')
  })

  it('names the earliest medium, and the picture when none is named', () => {
    expect(read('ein Lied über ein Bild').primary).toBe('sound')
    expect(read('ein roter Kreis').primary).toBe('image')
  })
})
