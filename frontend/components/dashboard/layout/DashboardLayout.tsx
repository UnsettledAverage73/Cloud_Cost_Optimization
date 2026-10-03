'use client'

import React, { memo } from 'react'
import { DashboardSidebar } from './DashboardSidebar'
import { MobileNavSheet } from './MobileNavSheet'
import { DashboardHeader } from './DashboardHeader'
import { useDashboardStore } from '@/stores/useDashboardStore'

interface DashboardLayoutProps {
  children: React.ReactNode
  onOpenCommandPalette: () => void
  onOpenCliInstall: () => void
  onOpenConnect: () => void
  onSwitchAccount: (account: any) => Promise<void>
}

export const DashboardLayout = memo(function DashboardLayout({
  children,
  onOpenCommandPalette,
  onOpenCliInstall,
  onOpenConnect,
  onSwitchAccount,
}: DashboardLayoutProps) {
  const collapsed = useDashboardStore((s) => s.collapsed)
  const light = useDashboardStore((s) => s.light)

  return (
    <div className={light ? 'light' : 'dark'}>
      <div className="min-h-screen bg-background text-foreground">
        {/* Desktop Pinned Sidebar */}
        <DashboardSidebar />

        {/* Mobile Navigation Sheet */}
        <MobileNavSheet />

        {/* Main Content Area */}
        <div className={`flex flex-col transition-all duration-200 ${collapsed ? 'lg:pl-20' : 'lg:pl-64'}`}>
          <DashboardHeader
            onOpenCommandPalette={onOpenCommandPalette}
            onOpenCliInstall={onOpenCliInstall}
            onOpenConnect={onOpenConnect}
            onSwitchAccount={onSwitchAccount}
          />
          <main className="flex-1 p-3 sm:p-4 md:p-6 lg:p-8 max-w-full">
            {children}
          </main>
        </div>
      </div>
    </div>
  )
})
