/**
 * Minimal hook runner for the node test environment (no DOM). It reproduces the part of React that
 * matters for request loops: state updates re-render, effects re-run only when a dependency
 * changes by Object.is. Use it with vi.mock('react', () => reactHarnessModule()).
 */
type Slot = { value?: unknown; deps?: unknown[] | undefined; cleanup?: (() => void) | void }

let current: Instance | null = null

class Instance {
  slots: Slot[] = []
  index = 0
  dirty = false
  pending: Array<() => void> = []
  renders = 0
  output: unknown
  fn: () => unknown
  /** Called with the rendered output before effects run: attach fake DOM nodes to refs here. */
  onRendered?: (output: unknown) => void
  constructor(fn: () => unknown) {
    this.fn = fn
  }

  render() {
    current = this
    this.index = 0
    this.renders += 1
    this.dirty = false
    this.output = this.fn()
    current = null
    this.onRendered?.(this.output)
    const run = this.pending
    this.pending = []
    run.forEach((effect) => effect())
  }
}

function slot(): { inst: Instance; s: Slot } {
  if (!current) throw new Error('hook outside render')
  const inst = current
  const s = (inst.slots[inst.index] ??= {})
  inst.index += 1
  return { inst, s }
}

function depsChanged(a: unknown[] | undefined, b: unknown[] | undefined): boolean {
  if (!a || !b) return true
  return a.length !== b.length || a.some((v, i) => !Object.is(v, b[i]))
}

export function useState<T>(init: T | (() => T)) {
  const { inst, s } = slot()
  if (!('value' in s)) s.value = typeof init === 'function' ? (init as () => T)() : init
  const set = (next: T | ((prev: T) => T)) => {
    const value = typeof next === 'function' ? (next as (p: T) => T)(s.value as T) : next
    if (!Object.is(value, s.value)) {
      s.value = value
      inst.dirty = true
    }
  }
  return [s.value as T, set] as const
}

export function useEffect(effect: () => void | (() => void), deps?: unknown[]) {
  const { inst, s } = slot()
  if (depsChanged(s.deps, deps)) {
    s.deps = deps
    inst.pending.push(() => {
      if (typeof s.cleanup === 'function') s.cleanup()
      s.cleanup = effect()
    })
  }
}

export function useMemo<T>(factory: () => T, deps: unknown[]): T {
  const { s } = slot()
  if (depsChanged(s.deps, deps)) {
    s.deps = deps
    s.value = factory()
  }
  return s.value as T
}

export function useCallback<T>(fn: T, deps: unknown[]): T {
  return useMemo(() => fn, deps)
}

export function useRef<T>(init: T) {
  const { s } = slot()
  if (!('value' in s)) s.value = { current: init }
  return s.value as { current: T }
}

let idCounter = 0
export function useId() {
  const { s } = slot()
  if (!('value' in s)) s.value = `:h${(idCounter += 1)}:`
  return s.value as string
}

export function reactHarnessModule() {
  return {
    useState,
    useEffect,
    useLayoutEffect: useEffect,
    useMemo,
    useCallback,
    useRef,
    useId,
    default: { useState, useEffect, useLayoutEffect: useEffect, useMemo, useCallback, useRef, useId },
  }
}

/** Renders `fn` and keeps re-rendering while state changes; each tick lets promises settle. */
export async function mountHook<T>(
  fn: () => T,
  ticks = 40,
  onRendered?: (output: unknown) => void,
) {
  const inst = new Instance(fn)
  inst.onRendered = onRendered
  inst.render()
  const settle = async (n = ticks) => {
    for (let i = 0; i < n; i += 1) {
      await new Promise((r) => setTimeout(r, 0))
      if (inst.dirty) inst.render()
    }
  }
  await settle()
  return {
    result: () => inst.output as T,
    renders: () => inst.renders,
    rerender: () => inst.render(),
    settle,
  }
}
