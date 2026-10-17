/**
 * Iceberg Physics Composable
 *
 * Provides polygon manipulation functions for the melting iceberg animation.
 * Own implementation - no external library dependencies (license-free).
 */

export interface Point {
  x: number
  y: number
}

/**
 * Calculate the centroid (center of mass) of a polygon
 * Uses the geometric centroid formula for irregular polygons
 */
export function calculateCentroid(polygon: Point[]): Point {
  if (polygon.length === 0) {
    return { x: 0, y: 0 }
  }

  const first = polygon[0]
  if (!first || polygon.length === 1) {
    return { x: first?.x ?? 0, y: first?.y ?? 0 }
  }

  let cx = 0
  let cy = 0
  let area = 0

  for (let i = 0; i < polygon.length; i++) {
    const j = (i + 1) % polygon.length
    const pi = polygon[i]
    const pj = polygon[j]
    if (!pi || !pj) continue

    const cross = pi.x * pj.y - pj.x * pi.y
    area += cross
    cx += (pi.x + pj.x) * cross
    cy += (pi.y + pj.y) * cross
  }

  area /= 2

  if (Math.abs(area) < 0.0001) {
    // Degenerate polygon - return average of points
    const avgX = polygon.reduce((sum, p) => sum + p.x, 0) / polygon.length
    const avgY = polygon.reduce((sum, p) => sum + p.y, 0) / polygon.length
    return { x: avgX, y: avgY }
  }

  cx /= 6 * area
  cy /= 6 * area

  return { x: cx, y: cy }
}

/**
 * Calculate the area of a polygon using the Shoelace formula
 */
export function calculateArea(polygon: Point[]): number {
  if (polygon.length < 3) return 0

  let area = 0
  for (let i = 0; i < polygon.length; i++) {
    const j = (i + 1) % polygon.length
    const pi = polygon[i]
    const pj = polygon[j]
    if (!pi || !pj) continue

    area += pi.x * pj.y
    area -= pj.x * pi.y
  }

  return Math.abs(area / 2)
}

/**
 * Simplify a polygon using Douglas-Peucker algorithm
 * Reduces the number of points while preserving shape
 *
 * @param polygon - Input polygon points
 * @param epsilon - Maximum distance threshold (higher = more simplification)
 * @returns Simplified polygon
 */
export function simplifyPolygon(polygon: Point[], epsilon: number = 2): Point[] {
  if (polygon.length <= 2) return polygon

  // Find the point with maximum distance from the line between first and last
  let maxDistance = 0
  let maxIndex = 0

  const start = polygon[0]
  const end = polygon[polygon.length - 1]

  if (!start || !end) return polygon

  for (let i = 1; i < polygon.length - 1; i++) {
    const point = polygon[i]
    if (!point) continue

    const distance = perpendicularDistance(point, start, end)
    if (distance > maxDistance) {
      maxDistance = distance
      maxIndex = i
    }
  }

  // If max distance is greater than epsilon, recursively simplify
  if (maxDistance > epsilon) {
    const left = simplifyPolygon(polygon.slice(0, maxIndex + 1), epsilon)
    const right = simplifyPolygon(polygon.slice(maxIndex), epsilon)

    // Combine results, avoiding duplicate point at maxIndex
    return [...left.slice(0, -1), ...right]
  }

  // Otherwise, return just the endpoints
  return [start, end]
}

/**
 * Calculate perpendicular distance from a point to a line segment
 */
function perpendicularDistance(point: Point, lineStart: Point, lineEnd: Point): number {
  const dx = lineEnd.x - lineStart.x
  const dy = lineEnd.y - lineStart.y

  if (dx === 0 && dy === 0) {
    // Line is a point
    return Math.sqrt(
      (point.x - lineStart.x) ** 2 + (point.y - lineStart.y) ** 2
    )
  }

  const lineLengthSquared = dx * dx + dy * dy

  // Calculate perpendicular distance using cross product method
  const cross = Math.abs(
    (point.y - lineStart.y) * dx - (point.x - lineStart.x) * dy
  )

  return cross / Math.sqrt(lineLengthSquared)
}

