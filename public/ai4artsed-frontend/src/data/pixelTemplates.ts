import templatesJson from './pixelTemplates.json'

export const GRID_SIZE = 14
export const MAX_COLOR_INDEX = 7

export type PixelPattern = number[][]

export const tokenColors = [
  '#3498db', '#9b59b6', '#e74c3c', '#2ecc71', '#f39c12', '#1abc9c', '#e91e63'
]

export const imageTemplates: Record<string, PixelPattern> = templatesJson
