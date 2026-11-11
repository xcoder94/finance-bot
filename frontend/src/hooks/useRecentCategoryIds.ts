import { useEffect, useState } from 'react'

import { fetchHistoryPage } from '../api/history'
import { addDays, dayEndIso, dayStartIso, todayTashkent } from '../utils/dateChips'
import {
  mergeRecentIds,
  readRecentCategories,
  recentIdsFromHistory,
  type RecentType,
} from '../utils/recentCategories'

const HISTORY_DAYS = 60
const HISTORY_LIMIT = 100

type CategoryLike = { id: string; name: string; translation_key?: string | null; parent_id?: string | null }

/**
 * Ids for the «recent categories» chips. The device's localStorage list is shown at once; when the
 * budget history arrives (existing API, no new endpoint) it replaces it, so entries made through
 * the bot and on other devices count too. A failed request keeps the local list.
 */
export function useRecentCategoryIds(
  budgetId: string,
  type: RecentType,
  categories: CategoryLike[],
  enabled: boolean,
): string[] {
  const [local] = useState(() => readRecentCategories(budgetId, type))
  const [fetched, setFetched] = useState<{ budgetId: string; items: Parameters<typeof recentIdsFromHistory>[0] } | null>(null)

  useEffect(() => {
    if (!enabled || !budgetId) {
      return
    }
    let cancelled = false
    const today = todayTashkent()
    void fetchHistoryPage(dayStartIso(addDays(today, -HISTORY_DAYS)), dayEndIso(today), HISTORY_LIMIT, 0)
      .then((response) => {
        if (!cancelled) {
          setFetched({ budgetId, items: response.items })
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [budgetId, enabled])

  const serverIds =
    fetched && fetched.budgetId === budgetId ? recentIdsFromHistory(fetched.items, categories, type) : []
  return mergeRecentIds(serverIds, local)
}
