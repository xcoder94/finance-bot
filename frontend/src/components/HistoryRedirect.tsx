import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { openHistoryTab } from '../utils/historyEntry'

/** The old address /history: the one operations list is the History tab of Analytics. */
export function HistoryRedirect() {
  const location = useLocation()
  useState(() => openHistoryTab())
  return <Navigate to="/analytics" replace state={location.state} />
}
