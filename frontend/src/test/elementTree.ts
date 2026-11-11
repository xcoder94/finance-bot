import type { ReactNode } from 'react'

/** Helpers to look at what a component returned (React elements) without a DOM. */
type El = { type: unknown; props: Record<string, unknown> }

function isElement(node: unknown): node is El {
  return typeof node === 'object' && node !== null && 'props' in node && 'type' in node
}

export function walk(node: ReactNode | unknown, visit: (el: El) => void): void {
  if (Array.isArray(node)) {
    node.forEach((child) => walk(child, visit))
    return
  }
  if (!isElement(node)) return
  visit(node)
  walk(node.props.children, visit)
}

export function findAll(node: unknown, pred: (el: El) => boolean): El[] {
  const found: El[] = []
  walk(node, (el) => {
    if (pred(el)) found.push(el)
  })
  return found
}

export function textOf(node: unknown): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isElement(node)) return textOf(node.props.children)
  return ''
}

export function findButton(node: unknown, text: string): El | undefined {
  return findAll(node, (el) => el.type === 'button' && textOf(el.props.children).includes(text))[0]
}

export type { El }
