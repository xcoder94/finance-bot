import { Route, Routes } from 'react-router-dom'

import { AnalyticsCategoriesPage } from './analytics/AnalyticsCategoriesPage'
import { AnalyticsCategoryDetailPage } from './analytics/AnalyticsCategoryDetailPage'
import { AnalyticsLayout } from './analytics/AnalyticsLayout'
import { AnalyticsMainPage } from './analytics/AnalyticsMainPage'

export default function AnalyticsPage() {
  return (
    <Routes>
      <Route element={<AnalyticsLayout />}>
        <Route index element={<AnalyticsMainPage />} />
        <Route path="categories" element={<AnalyticsCategoriesPage />} />
        <Route path="categories/:categoryKey" element={<AnalyticsCategoryDetailPage />} />
      </Route>
    </Routes>
  )
}
