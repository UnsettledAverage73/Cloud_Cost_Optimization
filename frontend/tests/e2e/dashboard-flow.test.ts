import { describe, it, expect, beforeEach, vi } from 'vitest'
import { validateForm, enrollAccountSchema } from '@/lib/validations/forms'
import { monitoring, captureException } from '@/lib/monitoring/logger'
import { useDashboardStore } from '@/stores/useDashboardStore'

describe('End-to-End Reliability & Flow Simulation', () => {
  beforeEach(() => {
    useDashboardStore.setState({
      view: 'overview',
      nodes: [],
      dataSources: {},
      lastFetchedAt: null,
      connectionReady: true,
      connectionState: { connected: true, status: 'success', message: '' },
    })
  })

  it('Flow 1: Form Validation Guardrail Blocks Malformed Fleet Input', () => {
    // User attempts to enroll with invalid short account ID
    const malformedPayload = {
      account_id: '999',
      account_name: '',
      region: 'invalid-region',
    }

    const validation = validateForm(enrollAccountSchema, malformedPayload)
    expect(validation.success).toBe(false)
    expect(validation.errors['account_id']).toBeDefined()

    // Validate that monitoring logs the event
    monitoring.addBreadcrumb({
      category: 'ui',
      message: 'Enrollment form submitted with invalid parameters',
      level: 'warning',
      data: validation.errors,
    })

    const crumbs = monitoring.getRecentBreadcrumbs()
    expect(crumbs[crumbs.length - 1].message).toContain('invalid parameters')
  })

  it('Flow 2: Valid Input Succeeds and Integrates with Store State', () => {
    // User submits valid inputs
    const validPayload = {
      account_id: '123456789012',
      account_name: 'Production Core Workloads',
      region: 'us-east-1',
      role_arn: 'arn:aws:iam::123456789012:role/CloudPulseRole',
      is_management_account: true,
    }

    const validation = validateForm(enrollAccountSchema, validPayload)
    expect(validation.success).toBe(true)
    expect(validation.data?.account_id).toBe('123456789012')
  })

  it('Flow 3: Resilience and Exception Monitoring under API Breakdown', async () => {
    // Simulate server crash on API
    const simulatedServerError = new Error('503 Service Unavailable: Database lock failure')
    const errorId = captureException(simulatedServerError, {
      component: 'FleetManager',
      tags: { route: '/api/v2/fleet/accounts' },
    })

    expect(errorId).toBeDefined()
    const recordedErrors = monitoring.getRecentErrors()
    expect(recordedErrors[0].message).toContain('503 Service Unavailable')
    expect(recordedErrors[0].component).toBe('FleetManager')
  })

  it('Flow 4: Cache Avoids Redundant Network Hits on Successive Invocations', async () => {
    let networkCallCount = 0
    global.fetch = vi.fn().mockImplementation(() => {
      networkCallCount++
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'healthy' }),
      })
    }) as any

    const apiUrl = (path: string) => `http://localhost:8000${path}`
    
    // First invocation: calls network
    await useDashboardStore.getState().fetchData(apiUrl)
    const initialCalls = networkCallCount
    expect(initialCalls).toBeGreaterThan(0)

    // Immediate second invocation within TTL: cache is used, no extra network hits
    await useDashboardStore.getState().fetchData(apiUrl, false)
    expect(networkCallCount).toBe(initialCalls)

    // Forced invocation: bypasses cache and hits network
    await useDashboardStore.getState().fetchData(apiUrl, true)
    expect(networkCallCount).toBeGreaterThan(initialCalls)
  })
})
