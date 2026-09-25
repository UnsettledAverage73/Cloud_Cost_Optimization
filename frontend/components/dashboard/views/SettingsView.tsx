'use client'

import { useState, useEffect, useCallback } from 'react'
import { Bell, History, Loader2, RefreshCw, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { SectionTitle } from '@/components/dashboard'
import type { ConnectionState, ConnectedAccount, CloudProfile } from '@/types/dashboard'

function connectionKey(account: any) {
  return [
    account?.provider || '',
    account?.account_name || '',
    account?.region || '',
    account?.role_arn || '',
    account?.access_key_last4 || '',
  ].join('::')
}

interface SettingsViewProps {
  connectionState?: ConnectionState
  connectedAccounts?: ConnectedAccount[]
  rememberedProfile?: CloudProfile | null
  onSwitchAccount?: (account: any) => void
  selectedAccountKey?: string
  apiUrl: (path: string) => string
}

export function SettingsView({
  connectionState,
  connectedAccounts = [],
  rememberedProfile,
  onSwitchAccount,
  selectedAccountKey,
  apiUrl,
}: SettingsViewProps) {
  const [orgName, setOrgName] = useState('')
  const [slackWebhookUrl, setSlackWebhookUrl] = useState('')
  const [teamsWebhookUrl, setTeamsWebhookUrl] = useState('')
  const [slackBotToken, setSlackBotToken] = useState('')
  const [slackChannel, setSlackChannel] = useState('all-average')
  const [whatsappTo, setWhatsappTo] = useState('')
  const [alertRules, setAlertRules] = useState({
    on_waste_found: true,
    on_batch_digest: true,
    on_anomaly: true,
    on_grace_period: true,
    on_sla_breach: true,
    on_gitops_pr: true,
  })
  const [deliveryHistory, setDeliveryHistory] = useState<any[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testingChannel, setTestingChannel] = useState<string | null>(null)
  const [testFeedback, setTestFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const fetchHistory = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const res = await fetch(apiUrl('/api/v2/notifications/history'))
      const data = await res.json()
      if (Array.isArray(data?.history)) {
        setDeliveryHistory(data.history)
      }
    } catch {
      // Ignore background error
    } finally {
      setLoadingHistory(false)
    }
  }, [apiUrl])

  useEffect(() => {
    let cancelled = false

    const loadSettings = async () => {
      try {
        const [settingsRes, configRes, historyRes] = await Promise.allSettled([
          fetch(apiUrl('/api/settings')),
          fetch(apiUrl('/api/v2/notifications/config')),
          fetch(apiUrl('/api/v2/notifications/history')),
        ])

        if (!cancelled && settingsRes.status === 'fulfilled') {
          const data = await settingsRes.value.json()
          setOrgName(data?.organization || '')
          setSlackWebhookUrl(data?.slack_webhook_url || '')
          setTeamsWebhookUrl(data?.teams_webhook_url || '')
          setSlackBotToken(data?.slack_bot_token || '')
          setSlackChannel(data?.slack_channel || 'all-average')
          setWhatsappTo(data?.whatsapp_to || '')
        }

        if (!cancelled && configRes.status === 'fulfilled') {
          const cfg = await configRes.value.json()
          if (cfg?.alert_rules) {
            setAlertRules((prev) => ({ ...prev, ...cfg.alert_rules }))
          }
          if (cfg?.slack_webhook_url && !slackWebhookUrl) setSlackWebhookUrl(cfg.slack_webhook_url)
          if (cfg?.teams_webhook_url && !teamsWebhookUrl) setTeamsWebhookUrl(cfg.teams_webhook_url)
        }

        if (!cancelled && historyRes.status === 'fulfilled') {
          const hist = await historyRes.value.json()
          if (Array.isArray(hist?.history)) {
            setDeliveryHistory(hist.history)
          }
        }
      } catch (err) {
        console.error('Failed to load settings:', err)
      } finally {
        if (!cancelled) {
          setLoaded(true)
        }
      }
    }

    loadSettings()

    return () => {
      cancelled = true
    }
  }, [apiUrl])

  const handleSave = async () => {
    setSaving(true)
    setTestFeedback(null)
    try {
      await Promise.all([
        fetch(apiUrl('/api/settings'), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            orgName,
            slackWebhookUrl,
            teamsWebhookUrl,
            slackBotToken,
            slackChannel,
            whatsappTo,
          }),
        }),
        fetch(apiUrl('/api/v2/notifications/config'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            slack_webhook_url: slackWebhookUrl,
            teams_webhook_url: teamsWebhookUrl,
            slack_bot_token: slackBotToken,
            slack_channel: slackChannel,
            whatsapp_to: whatsappTo,
            alert_rules: alertRules,
            enabled_channels: {
              slack: Boolean(slackWebhookUrl || slackBotToken),
              teams: Boolean(teamsWebhookUrl),
              whatsapp: Boolean(whatsappTo),
            },
          }),
        }),
      ])
      setTestFeedback({ type: 'success', message: 'All workspace & multi-channel notification policies saved successfully.' })
      fetchHistory()
    } catch (e: any) {
      setTestFeedback({ type: 'error', message: `Failed to save settings: ${e.message || e}` })
    } finally {
      setSaving(false)
    }
  }

  const testNotification = async (channel: 'slack' | 'teams') => {
    setTestingChannel(channel)
    setTestFeedback(null)
    try {
      const ep = channel === 'slack' ? '/api/v2/notifications/slack' : '/api/v2/notifications/teams'
      const targetUrl = channel === 'slack' ? slackWebhookUrl : teamsWebhookUrl
      const res = await fetch(apiUrl(ep), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource_id: 'i-0a106c14603cb65a0',
          finding_title: `CloudPulse Live ${channel === 'slack' ? 'Slack' : 'Microsoft Teams'} Test Alert`,
          severity: 'HIGH',
          current_monthly_spend: 68.4,
          potential_monthly_savings: 24.5,
          recommended_action: 'Downsize overprovisioned instance to Graviton t4g.small',
          webhook_url: targetUrl || undefined,
        }),
      })
      const data = await res.json()
      if (data.dispatched) {
        setTestFeedback({
          type: 'success',
          message: `✅ Test card dispatched and posted to ${channel === 'slack' ? 'Slack #' + (slackChannel || 'all-average') : 'Microsoft Teams'}!`,
        })
      } else {
        setTestFeedback({
          type: 'error',
          message: `⚠️ Card generated, but target ${channel === 'slack' ? 'Slack channel/token' : 'Teams webhook'} was not reachable.`,
        })
      }
      fetchHistory()
    } catch (err: any) {
      setTestFeedback({
        type: 'error',
        message: `❌ Failed to dispatch test alert: ${err?.message || err}`,
      })
    } finally {
      setTestingChannel(null)
    }
  }

  return (
    <>
      <SectionTitle
        eyebrow="Workspace settings"
        title="Settings & Multi-Channel Notifications"
        description="Manage organization access, cloud provider profiles, and Slack & Microsoft Teams alerts."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-white/8 bg-card/75 backdrop-blur-sm shadow-xl shadow-black/20">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Organization Profile</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="text-xs text-muted-foreground">
              {loaded ? 'Loaded from backend settings.' : 'Loading settings...'}
            </div>
            <label className="text-sm">
              Organization Name
              <Input
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="mt-2 border-white/10 bg-white/5 text-sm"
                placeholder="Acme Corp"
              />
            </label>
            <Button
              className="w-fit bg-sky-400 text-slate-950 hover:bg-sky-300 font-semibold text-xs"
              onClick={handleSave}
              disabled={saving || !loaded}
            >
              {saving ? 'Saving...' : 'Save Organization'}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/75 backdrop-blur-sm shadow-xl shadow-black/20">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <Bell className="size-4 text-sky-400" />
                Slack & Teams Escalations
              </CardTitle>
              <div className="flex items-center gap-1.5">
                <Badge
                  variant="outline"
                  className={
                    slackWebhookUrl || slackBotToken
                      ? 'border-emerald-400/40 text-emerald-300 bg-emerald-500/10'
                      : 'border-white/10 text-muted-foreground'
                  }
                >
                  Slack: {slackWebhookUrl || slackBotToken ? 'Connected' : 'Offline'}
                </Badge>
                <Badge
                  variant="outline"
                  className={
                    teamsWebhookUrl
                      ? 'border-indigo-400/40 text-indigo-300 bg-indigo-500/10'
                      : 'border-white/10 text-muted-foreground'
                  }
                >
                  Teams: {teamsWebhookUrl ? 'Connected' : 'Offline'}
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="text-xs text-muted-foreground">
              Slack Incoming Webhook URL
              <Input
                value={slackWebhookUrl}
                onChange={(e) => setSlackWebhookUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/T.../B.../..."
                className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
              />
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="text-xs text-muted-foreground">
                Slack Bot Token (Optional)
                <Input
                  value={slackBotToken}
                  onChange={(e) => setSlackBotToken(e.target.value)}
                  placeholder="xoxb-..."
                  className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
                />
              </label>
              <label className="text-xs text-muted-foreground">
                Slack Target Channel
                <Input
                  value={slackChannel}
                  onChange={(e) => setSlackChannel(e.target.value)}
                  placeholder="all-average"
                  className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
                />
              </label>
            </div>

            <label className="text-xs text-muted-foreground">
              Microsoft Teams Webhook URL (Power Automate / Workflows)
              <Input
                value={teamsWebhookUrl}
                onChange={(e) => setTeamsWebhookUrl(e.target.value)}
                placeholder="https://prod-xx.westus.logic.azure.com:443/workflows/.../invoke?..."
                className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
              />
            </label>

            <label className="text-xs text-muted-foreground">
              WhatsApp Escalation Phone (Twilio)
              <Input
                value={whatsappTo}
                onChange={(e) => setWhatsappTo(e.target.value)}
                placeholder="+91XXXXXXXXXX"
                className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
              />
            </label>

            {/* Notification Policy Toggles */}
            <div className="pt-2 border-t border-white/10">
              <div className="text-xs font-medium text-slate-200 mb-2">Automated Alert Triggers</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <label className="flex items-center gap-2 cursor-pointer text-muted-foreground hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={alertRules.on_anomaly}
                    onChange={(e) => setAlertRules({ ...alertRules, on_anomaly: e.target.checked })}
                    className="rounded border-white/20 bg-white/5 accent-sky-400"
                  />
                  <span>Spend Anomalies & Runaway Spikes</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-muted-foreground hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={alertRules.on_grace_period}
                    onChange={(e) => setAlertRules({ ...alertRules, on_grace_period: e.target.checked })}
                    className="rounded border-white/20 bg-white/5 accent-sky-400"
                  />
                  <span>10-Min Pre-Stop Grace Period Warnings</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-muted-foreground hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={alertRules.on_sla_breach}
                    onChange={(e) => setAlertRules({ ...alertRules, on_sla_breach: e.target.checked })}
                    className="rounded border-white/20 bg-white/5 accent-sky-400"
                  />
                  <span>Post-Remediation SLA Degradation</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-muted-foreground hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={alertRules.on_gitops_pr}
                    onChange={(e) => setAlertRules({ ...alertRules, on_gitops_pr: e.target.checked })}
                    className="rounded border-white/20 bg-white/5 accent-sky-400"
                  />
                  <span>GitOps Remediation PR Delivery</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-muted-foreground hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={alertRules.on_batch_digest}
                    onChange={(e) => setAlertRules({ ...alertRules, on_batch_digest: e.target.checked })}
                    className="rounded border-white/20 bg-white/5 accent-sky-400"
                  />
                  <span>Weekly / Scheduled Batch Digests</span>
                </label>
              </div>
            </div>

            {testFeedback && (
              <div
                className={`rounded-lg p-3 text-xs ${
                  testFeedback.type === 'success'
                    ? 'border border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                    : 'border border-rose-400/30 bg-rose-400/10 text-rose-300'
                }`}
              >
                {testFeedback.message}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2 pt-2">
              <Button
                size="sm"
                className="bg-sky-400 text-slate-950 hover:bg-sky-300 font-semibold text-xs"
                onClick={handleSave}
                disabled={saving || !loaded}
              >
                {saving ? 'Saving...' : 'Save Channels & Policies'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-white/10 bg-white/5 text-xs hover:bg-sky-400/10 hover:text-sky-300"
                onClick={() => testNotification('slack')}
                disabled={testingChannel !== null}
              >
                {testingChannel === 'slack' ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Send className="mr-1 size-3" />}
                Test Slack
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-white/10 bg-white/5 text-xs hover:bg-indigo-400/10 hover:text-indigo-300"
                onClick={() => testNotification('teams')}
                disabled={testingChannel !== null}
              >
                {testingChannel === 'teams' ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Send className="mr-1 size-3" />}
                Test Teams
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Notification Delivery Audit Log */}
        <Card className="border-white/8 bg-card/75 backdrop-blur-sm shadow-xl shadow-black/20 lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <History className="size-4 text-sky-400" />
              Recent Notification Deliveries & Audit Trail
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              className="border-white/10 bg-white/5 text-xs"
              onClick={fetchHistory}
              disabled={loadingHistory}
            >
              <RefreshCw className={`mr-1 size-3 ${loadingHistory ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            {deliveryHistory.length === 0 ? (
              <div className="py-6 text-center text-xs text-muted-foreground">
                No recent notification deliveries recorded. Test channels or wait for scheduled alerts.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/10 hover:bg-transparent">
                      <TableHead className="text-xs">Time (UTC)</TableHead>
                      <TableHead className="text-xs">Channel</TableHead>
                      <TableHead className="text-xs">Target Destination</TableHead>
                      <TableHead className="text-xs">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {deliveryHistory.slice(0, 8).map((d: any, idx: number) => (
                      <TableRow key={d.id || idx} className="border-white/5 text-xs">
                        <TableCell className="font-mono text-muted-foreground">
                          {d.iso_time || (d.timestamp ? new Date(d.timestamp * 1000).toISOString().replace('T', ' ').slice(0, 19) : 'Just now')}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={d.channel?.includes('slack') ? 'border-sky-400/30 text-sky-300' : 'border-indigo-400/30 text-indigo-300'}>
                            {d.channel?.toUpperCase() || 'WEBHOOK'}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-muted-foreground">
                          {d.target || 'all-average'}
                        </TableCell>
                        <TableCell>
                          <Badge className={d.status === 'DELIVERED' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}>
                            {d.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/75 backdrop-blur-sm shadow-xl shadow-black/20 lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Connected Cloud Profiles</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {connectionState?.connected ? (
              <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4">
                <div className="text-sm font-medium text-emerald-200">{connectionState.account_name || 'Connected account'}</div>
                <div className="mt-1 text-xs text-emerald-100/80">
                  {connectionState.provider || 'AWS'} · {connectionState.region || 'us-east-1'}
                </div>
                {connectionState.role_arn && (
                  <div className="mt-2 font-mono text-[11px] text-emerald-100/70">{connectionState.role_arn}</div>
                )}
                <div className="mt-3 text-xs text-emerald-100/70">
                  Active profile is restored from backend storage after refresh.
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-muted-foreground">
                No AWS account is connected yet.
              </div>
            )}

            <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Saved connections
            </div>
            <div className="flex flex-col gap-3">
              {(Array.isArray(connectedAccounts) && connectedAccounts.length > 0) ? (
                connectedAccounts.map((account: any, idx: number) => (
                  <div
                    key={`${account.account_name || account.provider || 'account'}-${idx}`}
                    className={`rounded-lg border p-4 ${account.active ? 'border-sky-400/30 bg-sky-400/10' : 'border-white/10 bg-white/5'}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium">{account.account_name || 'Connected account'}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {account.provider || 'AWS'} · {account.region || 'us-east-1'}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {account.active && <Badge className="bg-sky-400 text-slate-950 font-semibold">Active</Badge>}
                        {!account.active && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="border-white/10 bg-white/5 text-xs"
                            onClick={() => onSwitchAccount?.(account)}
                            disabled={connectionKey(account) === selectedAccountKey}
                          >
                            Switch
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="mt-3 text-xs text-muted-foreground">
                      {account.auth_method || 'keys'}{account.session_token_present ? ' · session token saved' : ''}
                    </div>
                    {account.role_arn && (
                      <div className="mt-2 font-mono text-[11px] text-muted-foreground">{account.role_arn}</div>
                    )}
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-muted-foreground">
                  Saved connections will appear here after you connect an AWS account.
                </div>
              )}
            </div>
            <div className="rounded-lg border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Remembered login profile</div>
              {rememberedProfile ? (
                <div className="mt-3">
                  <div className="text-sm font-medium">{rememberedProfile.account_name || 'Connected account'}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {rememberedProfile.provider || 'AWS'} · {rememberedProfile.region || 'us-east-1'} · {rememberedProfile.auth_method || 'learner_lab'}
                  </div>
                  {rememberedProfile.role_arn && (
                    <div className="mt-2 font-mono text-[11px] text-muted-foreground">{rememberedProfile.role_arn}</div>
                  )}
                  <div className="mt-2 text-xs text-muted-foreground">
                    This profile is saved for prefill only. Secrets stay in the backend connection store.
                  </div>
                </div>
              ) : (
                <div className="mt-3 text-sm text-muted-foreground">No remembered profile yet.</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
export default SettingsView
