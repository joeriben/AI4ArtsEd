/**
 * The name of a language model under the axis of a chart, cut into lines in
 * ONE place for every chart that draws one (`components/ModelAxisLabel.vue`,
 * docs/ELEMENT_STRUCTURE_REGISTRY.md). SVG text does not wrap, so CSS alone
 * cannot break it: the name keeps the first line, and from the first bracket
 * after it the rest goes on a line of its own. "Qwen1.5 7B (02/2024)" becomes
 * "Qwen1.5 7B" over "(02/2024)". At the width of the iPad (a window of 1194
 * px) a slot of five models is 112 px wide, and the names of the generation
 * lineup, name and date on one line, ran into each other.
 */

/**
 * The step from one line of a model's name to the next, in viewBox units (one
 * unit is one pixel): one rem, the root font size, which follows the reader's
 * own font setting (16 px at the browser's default). The name's font,
 * `--flow-fs-label`, is at most 0.875 rem, so the two lines keep the same room
 * between them at every setting; a step fixed in pixels made them touch from a
 * root of about 18 px on.
 */
export function modelLabelLine(): number {
  return parseFloat(getComputedStyle(document.documentElement).fontSize)
}

/** The lines of one model's name: the name, and what follows it from the first bracket on. */
export function modelLabelLines(label: string): string[] {
  const cut = label.indexOf(' (')
  if (cut <= 0) return [label]
  return [label.slice(0, cut).trimEnd(), label.slice(cut + 1)]
}

/**
 * How far whatever a chart sets under the names has to move down: the lines
 * the longest name has beyond its first. Every model of a lineup stands at the
 * same height, so the score lines under them stay in one row.
 */
export function modelLabelDrop(labels: string[]): number {
  const rows = labels.reduce((n, label) => Math.max(n, modelLabelLines(label).length), 1)
  return rows > 1 ? (rows - 1) * modelLabelLine() : 0
}
