'use client'

import { useEffect } from 'react'
import { monitoring } from '@/lib/monitoring/logger'

export function MonitoringProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    monitoring.init()
  }, [])

  return <>{children}</>
}
