'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { DashboardLayout } from '@/components/dashboard/layout/DashboardLayout'
import { DashboardViewRouter } from '@/components/dashboard/router/DashboardViewRouter'
import { InstanceDetailDrawer } from '@/components/dashboard/InstanceDetailDrawer'
import { ConnectModal } from '@/components/dashboard/modals/ConnectModal'
import { CommandPaletteModal } from '@/components/dashboard/modals/CommandPaletteModal'
import { CliInstallModal } from '@/components/dashboard/modals/CliInstallModal'
import { useDashboardStore } from '@/stores/useDashboardStore'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import { apiUrl, formatCurrency } from '@/lib/formatters'
import { connectionKey } from '@/lib/constants'

export default function Page() {
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)
  const [cliModalOpen, setCliModalOpen] = useState(false)

  // Atomic Zustand Selectors for maximum 60fps rendering efficiency
  const view = useDashboardStore((s) => s.view)
  const setView = useDashboardStore((s) => s.setView)
  const light = useDashboardStore((s) => s.light)
  const currency = useDashboardStore((s) => s.currency)
  const setCurrency = useDashboardStore((s) => s.setCurrency)
  const connectOpen = useDashboardStore((s) => s.connectOpen)
  const setConnectOpen = useDashboardStore((s) => s.setConnectOpen)
  const connectionState = useDashboardStore((s) => s.connectionState)
  const setConnectionState = useDashboardStore((s) => s.setConnectionState)
  const connectedAccounts = useDashboardStore((s) => s.connectedAccounts)
  const setConnectedAccounts = useDashboardStore((s) => s.setConnectedAccounts)
  const rememberedProfile = useDashboardStore((s) => s.rememberedProfile)
  const setRememberedProfile = useDashboardStore((s) => s.setRememberedProfile)
  const selectedAccountKey = useDashboardStore((s) => s.selectedAccountKey)
  const setSelectedAccountKey = useDashboardStore((s) => s.setSelectedAccountKey)
  const autoRefresh = useDashboardStore((s) => s.autoRefresh)
  const autoRefreshIntervalSec = useDashboardStore((s) => s.autoRefreshIntervalSec)
  const storeFetchData = useDashboardStore((s) => s.fetchData)
  const setSyncing = useDashboardStore((s) => s.setSyncing)
  const setDataError = useDashboardStore((s) => s.setDataError)
  const nodes = useDashboardStore((s) => s.nodes)
  const selectedNode = useDashboardStore((s) => s.selectedNode)
  const setSelectedNode = useDashboardStore((s) => s.setSelectedNode)
  const selectedNodeDetail = useDashboardStore((s) => s.selectedNodeDetail)
  const setSelectedNodeDetail = useDashboardStore((s) => s.setSelectedNodeDetail)
  const setSelectedNodeTelemetry = useDashboardStore((s) => s.setSelectedNodeTelemetry)
  const selectedNodeLoading = useDashboardStore((s) => s.selectedNodeLoading)
  const setSelectedNodeLoading = useDashboardStore((s) => s.setSelectedNodeLoading)
  const revokeSecurityGroupLocally = useDashboardStore((s) => s.revokeSecurityGroupLocally)

  const { toast } = useOptimisticToast()

  // 1. Theme Synchronization
  useEffect(() => {
    if (typeof document !== 'undefined') {
      if (light) {
        document.documentElement.classList.add('light')
        document.documentElement.classList.remove('dark')
      } else {
        document.documentElement.classList.add('dark')
        document.documentElement.classList.remove('light')
      }
    }
  }, [light])

  // 2. Global Hotkey: Cmd+K / Ctrl+K / '/' for Command Palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandPaletteOpen((prev) => !prev)
      } else if (
        e.key === '/' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault()
        setCommandPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // 3. Initial Active Account Sync
  useEffect(() => {
    const activeAccount = connectedAccounts.find((account) => account?.active)
    if (activeAccount) {
      setSelectedAccountKey(connectionKey(activeAccount))
      return
    }

    if (connectionState?.connected) {
      setSelectedAccountKey(connectionKey(connectionState))
    }
  }, [
    connectedAccounts,
    connectionState?.connected,
    connectionState?.provider,
    connectionState?.account_name,
    connectionState?.region,
    connectionState?.role_arn,
    setSelectedAccountKey,
  ])

  // 4. Initial Mount Data Fetch
  const fetchData = useCallback(
    async (force = false) => {
      await storeFetchData(apiUrl, force)
    },
    [storeFetchData]
  )

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 5. Autonomous Auto-Refresh Polling Engine
  useEffect(() => {
    if (!connectionState?.connected || !autoRefresh) return

    const intervalMs = Math.max(10, autoRefreshIntervalSec || 60) * 1000
    const interval = window.setInterval(() => {
      fetchData(false)
    }, intervalMs)

    return () => window.clearInterval(interval)
  }, [connectionState?.connected, autoRefresh, autoRefreshIntervalSec, fetchData])

  // 6. Selected Node Telemetry & Specification Fetcher
  useEffect(() => {
    if (!selectedNode?.instance_id) {
      setSelectedNodeDetail(null)
      setSelectedNodeTelemetry([])
      setSelectedNodeLoading(false)
      return
    }

    let cancelled = false

    const loadNodeDetails = async () => {
      setSelectedNodeLoading(true)
      try {
        const [detailRes, telemetryRes] = await Promise.all([
          fetch(apiUrl(`/api/v1/resources/nodes/${selectedNode.instance_id}`)).then((res) => res.json()),
          fetch(apiUrl(`/api/v1/telemetry/${selectedNode.instance_id}`)).then((res) => res.json()),
        ])

        if (cancelled) return
        setSelectedNodeDetail(detailRes)
        setSelectedNodeTelemetry(Array.isArray(telemetryRes?.metrics) ? telemetryRes.metrics : [])
      } catch (err) {
        console.error('Error fetching node details:', err)
        if (!cancelled) {
          setSelectedNodeDetail(selectedNode)
          setSelectedNodeTelemetry([])
        }
      } finally {
        if (!cancelled) {
          setSelectedNodeLoading(false)
        }
      }
    }

    loadNodeDetails()

    return () => {
      cancelled = true
    }
  }, [selectedNode?.instance_id, setSelectedNodeDetail, setSelectedNodeLoading, setSelectedNodeTelemetry])

  // 7. Security Ingress Revocation Callback
  const handleDrawerRevoke = useCallback(
    async (sg: any) => {
      if (!sg?.group_id) return
      const targetId = sg.group_id
      const targetName = sg.group_name || targetId

      revokeSecurityGroupLocally?.(targetId)
      toast({
        title: 'Security Ingress Revoked',
        description: `Closed public 0.0.0.0/0 exposure on ${targetName}. Dispatched rule deletion to AWS.`,
        type: 'security',
      })

      try {
        const endpoint = apiUrl('/api/security/revoke')
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ groupId: targetId, groupName: targetName }),
        })
        if (res.ok) {
          await storeFetchData(apiUrl, true)
        } else {
          const err = await res.json().catch(() => ({}))
          toast({
            title: 'Revocation Failed',
            description: err.detail || 'Failed to revoke security group on provider.',
            type: 'error',
          })
        }
      } catch (e: any) {
        toast({
          title: 'Network Sync Error',
          description: e?.message || 'Network error while contacting CloudPulse backend.',
          type: 'error',
        })
      }
    },
    [revokeSecurityGroupLocally, storeFetchData, toast]
  )

  // 8. Multi-Account Switcher Callback
  const switchAccount = useCallback(
    async (account: any) => {
      if (!account) return
      const nextKey = connectionKey(account)
      if (nextKey === selectedAccountKey) return

      setSyncing(true)
      setDataError('')
      try {
        const res = await fetch(apiUrl('/api/v1/connect-cloud/switch'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: account.provider,
            account_name: account.account_name,
            region: account.region,
            role_arn: account.role_arn,
            access_key_last4: account.access_key_last4,
          }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.detail || 'Failed to switch AWS account')
        }

        const connection = data?.connection || {}
        const accounts = Array.isArray(data?.connected_accounts) ? data.connected_accounts : []
        const profile = {
          provider: connection.provider || account.provider,
          account_name: connection.account_name || account.account_name,
          auth_method: connection.auth_method || account.auth_method || 'learner_lab',
          region: connection.region || account.region,
          role_arn: connection.role_arn || account.role_arn,
          connected_at: new Date().toISOString(),
        }

        setConnectionState({
          connected: true,
          status: connection.status || 'success',
          message: connection.message || 'Switched AWS account',
          provider: profile.provider,
          account_name: profile.account_name,
          region: profile.region,
          role_arn: profile.role_arn,
          access_mode: connection.access_mode || 'live',
          warning: connection.warning || '',
        })
        setConnectedAccounts(accounts)
        setSelectedAccountKey(nextKey)
        setRememberedProfile(profile)

        toast({
          title: 'Switched Account',
          description: `Now monitoring: ${profile.account_name} (${profile.region})`,
          type: 'success',
        })
        await storeFetchData(apiUrl, true)
      } catch (err: any) {
        setDataError(err?.message || 'Failed to switch account')
        toast({
          title: 'Account Switch Failed',
          description: err?.message || 'Unable to switch active AWS account.',
          type: 'error',
        })
      } finally {
        setSyncing(false)
      }
    },
    [
      selectedAccountKey,
      setConnectionState,
      setConnectedAccounts,
      setDataError,
      setRememberedProfile,
      setSelectedAccountKey,
      setSyncing,
      storeFetchData,
      toast,
    ]
  )

  return (
    <>
      <DashboardLayout
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        onOpenCliInstall={() => setCliModalOpen(true)}
        onOpenConnect={() => setConnectOpen(true)}
        onSwitchAccount={switchAccount}
      >
        <DashboardViewRouter
          onOpenConnect={() => setConnectOpen(true)}
          onSwitchAccount={switchAccount}
        />
      </DashboardLayout>

      {/* Slide-over Instance Detail Inspection Drawer */}
      <InstanceDetailDrawer
        open={Boolean(selectedNode)}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            setSelectedNode(null)
            setSelectedNodeDetail(null)
            setSelectedNodeTelemetry([])
          }
        }}
        node={selectedNode}
        nodeDetail={selectedNodeDetail}
        loading={selectedNodeLoading}
        currency={currency}
        rate={84.0}
        apiUrl={apiUrl}
        formatCurrency={formatCurrency}
        onRevokeSg={handleDrawerRevoke}
        onOpenFullTelemetry={() => {
          setSelectedNode(null)
          setSelectedNodeDetail(null)
          setSelectedNodeTelemetry([])
          setView('telemetry')
        }}
      />

      {/* Cloud Account Connect Modal */}
      <ConnectModal
        open={connectOpen}
        onOpenChange={setConnectOpen}
        initialProfile={rememberedProfile}
        apiUrl={apiUrl}
        onSuccess={(payload: any) => {
          const connection = payload?.connection || payload || {}
          const accounts = Array.isArray(payload?.connected_accounts)
            ? payload.connected_accounts
            : Array.isArray(connection?.connected_accounts)
            ? connection.connected_accounts
            : []
          setConnectionState({
            connected: Boolean(connection.connected ?? true),
            status: connection.status || 'success',
            message: connection.message || 'Success',
            provider: connection.provider || payload?.provider || 'AWS',
            account_name: connection.account_name || payload?.account_name || '',
            region: connection.region || payload?.region || 'us-east-1',
            role_arn: connection.role_arn || payload?.role_arn,
            access_mode: connection.access_mode || payload?.access_mode || 'live',
            warning: connection.warning || payload?.warning || '',
          })
          setConnectedAccounts(accounts)
          const profile = {
            provider: connection.provider || payload?.provider || 'AWS',
            account_name: connection.account_name || payload?.account_name || '',
            auth_method: connection.auth_method || payload?.auth_method || 'learner_lab',
            region: connection.region || payload?.region || 'us-east-1',
            role_arn: connection.role_arn || payload?.role_arn || '',
            connected_at: new Date().toISOString(),
          }
          setRememberedProfile(profile)
          fetchData(true)
        }}
      />

      {/* Global Command Palette Modal */}
      <CommandPaletteModal
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
        currentView={view}
        onSelectView={setView}
        nodes={nodes}
        onSelectNode={(node) => setSelectedNode(node)}
        onToggleCurrency={() => {
          const next = currency === 'USD' ? 'INR' : 'USD'
          setCurrency(next)
          toast({
            title: `Currency: ${next}`,
            description: `Active display currency changed to ${next}.`,
            type: 'info',
          })
        }}
        currency={currency}
        onOpenCliInstall={() => setCliModalOpen(true)}
      />

      {/* CLI Installation Instruction Modal */}
      <CliInstallModal
        open={cliModalOpen}
        onOpenChange={setCliModalOpen}
        backendUrl={apiUrl('') || 'https://cloud-cost-optimization.onrender.com'}
      />
    </>
  )
}