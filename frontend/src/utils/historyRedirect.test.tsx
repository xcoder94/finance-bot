import { beforeEach, describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { HistoryRedirect } from '../components/HistoryRedirect'
import { useAnalyticsShellStore } from '../store/analyticsShellStore'

beforeEach(() => {
  useAnalyticsShellStore.setState({ shell: null })
})

describe('/history route', () => {
  it('opens the History tab of Analytics (old links keep working)', () => {
    renderToStaticMarkup(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="history" element={<HistoryRedirect />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(useAnalyticsShellStore.getState().shell?.activeTab).toBe('history')
  })
})
