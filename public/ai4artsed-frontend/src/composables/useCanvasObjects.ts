import { ref, type Ref } from 'vue'

/**
 * Base interface for Canvas objects
 */
export interface CanvasObject {
  /** Unique identifier */
  id: string | number

  /** X position */
  x: number

  /** Y position */
  y: number

  /**
   * Render this object to canvas
   * @param ctx - Canvas 2D context
   */
  render: (ctx: CanvasRenderingContext2D) => void

  /**
   * Optional update function (called each tick)
   * @param dt - Delta time in seconds
   */
  update?: (dt: number) => void
}

/**
 * Canvas object management composable
 *
 * Provides utilities for managing dynamic Canvas objects (trees, factories, particles, etc.)
 *
 * @example
 * ```typescript
 * interface Tree extends CanvasObject {
 *   type: 'pine' | 'oak'
 *   scale: number
 *   health: 'healthy' | 'sick'
 * }
 *
 * const { objects: trees, addObject, removeObject, updateAll, renderAll } = useCanvasObjects<Tree>()
 *
 * // Add tree
 * addObject({
 *   id: Date.now(),
 *   x: 100,
 *   y: 200,
 *   type: 'pine',
 *   scale: 1.0,
 *   health: 'healthy',
 *   render: (ctx) => {
 *     // Draw tree
 *   }
 * })
 *
 * // Game loop
 * function tick(dt: number) {
 *   updateAll(dt)
 * }
 *
 * function render(ctx: CanvasRenderingContext2D) {
 *   renderAll(ctx)
 * }
 * ```
 */
export function useCanvasObjects<T extends CanvasObject>() {
  const objects = ref<T[]>([]) as Ref<T[]>

  /**
   * Add object to the collection
   */
  function addObject(obj: T) {
    objects.value.push(obj)
  }

  /**
   * Remove object by ID
   */
  function removeObject(id: string | number) {
    objects.value = objects.value.filter(obj => obj.id !== id)
  }

  /**
   * Remove object by reference
   */
  function removeObjectByRef(obj: T) {
    const index = objects.value.indexOf(obj)
    if (index !== -1) {
      objects.value.splice(index, 1)
    }
  }

  /**
   * Remove objects matching a predicate
   */
  function removeWhere(predicate: (obj: T) => boolean) {
    objects.value = objects.value.filter(obj => !predicate(obj))
  }

  /**
   * Find object by ID
   */
  function findById(id: string | number): T | undefined {
    return objects.value.find(obj => obj.id === id)
  }

  /**
   * Find objects matching a predicate
   */
  function findWhere(predicate: (obj: T) => boolean): T[] {
    return objects.value.filter(predicate)
  }

  /**
   * Clear all objects
   */
  function clear() {
    objects.value = []
  }

  /**
   * Update all objects (calls obj.update if defined)
   */
  function updateAll(dt: number) {
    objects.value.forEach(obj => {
      if (obj.update) {
        obj.update(dt)
      }
    })
  }

  /**
   * Render all objects (calls obj.render)
   */
  function renderAll(ctx: CanvasRenderingContext2D) {
    objects.value.forEach(obj => {
      obj.render(ctx)
    })
  }

  /**
   * Sort objects (useful for z-ordering)
   *
   * @example Sort by y position (back to front)
   * ```typescript
   * sortObjects((a, b) => a.y - b.y)
   * ```
   */
  function sortObjects(compareFn: (a: T, b: T) => number) {
    objects.value.sort(compareFn)
  }

  /**
   * Get count of objects
   */
  function count(): number {
    return objects.value.length
  }

  return {
    /** Reactive array of objects */
    objects,

    /** Add/remove operations */
    addObject,
    removeObject,
    removeObjectByRef,
    removeWhere,
    clear,

    /** Query operations */
    findById,
    findWhere,
    count,

    /** Batch operations */
    updateAll,
    renderAll,
    sortObjects
  }
}
