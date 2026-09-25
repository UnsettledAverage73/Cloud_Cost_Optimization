'use client'

import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { validateForm, connectCloudSchema } from '@/lib/validations/forms'
import { addBreadcrumb, captureException } from '@/lib/monitoring/logger'

const PROFILE_STORAGE_KEY = 'cloudpulse-remembered-profile'

function readStoredProfile() {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY)
    return null
  }
}

interface ConnectModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: (payload: any) => void
  initialProfile?: any
  apiUrl: (path: string) => string
}

export function ConnectModal({ open, onOpenChange, onSuccess, initialProfile, apiUrl }: ConnectModalProps) {
  const [cloud, setCloud] = useState('AWS')
  const [accountName, setAccountName] = useState('')
  const [authMethod, setAuthMethod] = useState('learner_lab')
  const [accessKey, setAccessKey] = useState('')
  const [secretKey, setSecretKey] = useState('')
  const [sessionToken, setSessionToken] = useState('')
  const [roleArn, setRoleArn] = useState('')
  const [region, setRegion] = useState('us-east-1')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!open) return
    const profile = initialProfile || readStoredProfile()
    if (!profile) return
    setCloud(profile.provider || 'AWS')
    setAccountName(profile.account_name || '')
    setAuthMethod(profile.auth_method || 'learner_lab')
    setRoleArn(profile.role_arn || '')
    setRegion(profile.region || 'us-east-1')
    setFieldErrors({})
  }, [open, initialProfile])

  const connect = async () => {
    let payload: any = {
      provider: 'AWS',
      account_name: accountName,
      region,
      auth_method: authMethod,
    }
    if (authMethod === 'learner_lab') {
      payload.access_key_id = accessKey
      payload.secret_access_key = secretKey
      payload.session_token = sessionToken
    } else if (authMethod === 'iam_role') {
      payload.role_arn = roleArn
    } else {
      payload.access_key_id = accessKey
      payload.secret_access_key = secretKey
    }

    if (cloud === 'AWS') {
      const validation = validateForm(connectCloudSchema, payload)
      if (!validation.success) {
        setFieldErrors(validation.errors)
        setError(Object.values(validation.errors)[0] || 'Invalid inputs')
        addBreadcrumb({
          category: 'ui',
          message: 'Cloud connection rejected by client validation',
          level: 'warning',
          data: validation.errors,
        })
        return
      }
    }

    setFieldErrors({})
    setLoading(true)
    setError('')
    setSuccess('')
    addBreadcrumb({
      category: 'api',
      message: `Connecting cloud account: ${accountName || 'Unnamed'} (${authMethod})`,
      level: 'info',
    })

    try {
      const res = await fetch(apiUrl('/api/v1/connect-cloud'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: cloud,
          account_name: accountName,
          auth_method: authMethod,
          access_key: accessKey,
          secret_key: secretKey,
          session_token: sessionToken,
          role_arn: roleArn,
          region,
        }),
      })
      if (res.ok) {
        const data = await res.json().catch(() => ({}))
        setSuccess(data?.message || 'Success')
        onSuccess?.({
          ...data,
          provider: data?.connection?.provider || data?.provider || cloud,
          account_name: data?.connection?.account_name || accountName,
          region: data?.connection?.region || region,
          auth_method: authMethod,
          role_arn: roleArn,
        })
        window.setTimeout(() => onOpenChange(false), 700)
      } else {
        const data = await res.json().catch(() => ({}))
        setError(data?.detail || 'Connection failed')
      }
    } catch (err) {
      console.error('Failed to connect account:', err)
      captureException(err, { component: 'ConnectModal', extra: { cloud, authMethod, accountName } })
      setError('Failed to connect account')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-white/10 bg-card sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Connect a cloud account</DialogTitle>
          <DialogDescription>Give CloudPulse read-only access to start syncing your infrastructure.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 pt-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              Cloud provider
              <Select value={cloud} onValueChange={(value) => setCloud(value ?? 'AWS')}>
                <SelectTrigger className="mt-2 w-full border-white/10 bg-white/5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AWS">AWS</SelectItem>
                  <SelectItem value="GCP">GCP</SelectItem>
                  <SelectItem value="Azure">Azure</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="text-sm">
              Auth method
              <Select value={authMethod} onValueChange={(value) => setAuthMethod(value ?? 'learner_lab')}>
                <SelectTrigger className="mt-2 w-full border-white/10 bg-white/5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="learner_lab">Learner Lab</SelectItem>
                  <SelectItem value="keys">Access keys</SelectItem>
                  <SelectItem value="iam_role">IAM role</SelectItem>
                </SelectContent>
              </Select>
            </label>
          </div>
          <label className="text-sm">
            Account name
            <Input value={accountName} onChange={(e) => setAccountName(e.target.value)} placeholder="Acme production" className="mt-2 border-white/10 bg-white/5" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              Access key
              <Input value={accessKey} onChange={(e) => setAccessKey(e.target.value)} placeholder="AKIA..." className="mt-2 border-white/10 bg-white/5" />
            </label>
            <label className="text-sm">
              Secret key
              <Input value={secretKey} onChange={(e) => setSecretKey(e.target.value)} placeholder="••••••••••••••••" type="password" className="mt-2 border-white/10 bg-white/5" />
            </label>
          </div>
          <label className="text-sm">
            Session token
            <Input value={sessionToken} onChange={(e) => setSessionToken(e.target.value)} placeholder="Temporary session token" className="mt-2 border-white/10 bg-white/5" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              IAM Role ARN / Identifier
              <Input value={roleArn} onChange={(e) => setRoleArn(e.target.value)} placeholder="arn:aws:iam::123456789:role/CloudPulseReadOnly" className="mt-2 border-white/10 bg-white/5" />
            </label>
            <label className="text-sm">
              Region
              <Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" className="mt-2 border-white/10 bg-white/5" />
            </label>
          </div>
          {error && (
            <div className="rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-sm text-emerald-200">
              {success}
            </div>
          )}
          <Button onClick={connect} disabled={loading} className="mt-2 bg-sky-400 text-slate-950 hover:bg-sky-300 font-semibold">
            {loading ? <><RefreshCw className="animate-spin mr-1.5 size-4" />Testing connection...</> : 'Connect Account'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
