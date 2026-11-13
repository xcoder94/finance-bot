type Cat = { id: string; name: string; translation_key?: string | null; parent_id?: string | null }

const norm = (value: string) => value.trim().toLocaleLowerCase()

function sameCategory(a: Cat, b: Cat): boolean {
  if (a.translation_key && b.translation_key) return a.translation_key === b.translation_key
  return norm(a.name) === norm(b.name)
}

/**
 * After a family change: the category the person picked in the old budget, found in the new one
 * (same translation key or same name; a subcategory also needs a matching parent). null if there is none.
 */
export function matchCategoryInBudget(oldList: Cat[], newList: Cat[], oldId: string): string | null {
  const old = oldList.find((item) => item.id === oldId)
  if (!old) return null
  const oldParent = old.parent_id ? oldList.find((item) => item.id === old.parent_id) : null
  const found = newList.find((item) => {
    if (!sameCategory(old, item)) return false
    const parent = item.parent_id ? newList.find((p) => p.id === item.parent_id) : null
    if (Boolean(oldParent) !== Boolean(parent)) return false
    return !oldParent || !parent || sameCategory(oldParent, parent)
  })
  return found?.id ?? null
}
