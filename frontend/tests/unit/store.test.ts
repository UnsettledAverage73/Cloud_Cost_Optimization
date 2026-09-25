import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useDashboardStore } from '@/stores/useDashboardStore'

describe('Zustand Dashboard Store & Caching Orchestrator', () => {
  beforeEach(() => {
    // Reset store state
    useDashboardStore.setState({
      view: 'overview',
      currency: 'USD',
      provider: 'all',
      search: '',
      status: 'all',
      connectionState: { connected: false, status: 'disconnected', message: '' },
      connectionReady: false,
      nodes: [],
      summary: null,
      dataSources: {},
      lastFetchedAt: null,
      syncing: false,
      loading: true,
      dataError: '',
    })
  })

  it('updates view, currency, and search query', () => {
    const { setView, setCurrency, setSearch } = useDashboardStore.getState()

    setView('fleet')
    expect(useDashboardStore.getState().view).toBe('fleet')

    setCurrency('INR')
    expect(useDashboardStore.getState().currency).toBe('INR')

    setSearch('i-012345')
    expect(useDashboardStore.getState().search).toBe('i-012345')
  })

  it('invalidates cache when cloud provider changes', () => {
    useDashboardStore.setState({ lastFetchedAt: Date.now() })
    expect(useDashboardStore.getState().lastFetchedAt).not.toBeNull()

    const { setProvider } = useDashboardStore.getState()
    setProvider('AWS')

    expect(useDashboardStore.getState().provider).toBe('AWS')
    expect(useDashboardStore.getState().lastFetchedAt).toBeNull()
  })

  it('does not fetch live data when disconnected and sets guidance message', async () => {
    useDashboardStore.setState({ connectionReady: true, connectionState: { connected: false, status: 'disconnected', message: '' } })
    const { fetchData } = useDashboardStore.getState()

    const mockApiUrl = vi.fn()
    await fetchData(mockApiUrl)

    expect(mockApiUrl).not.toHaveBeenCalled()
    expect(useDashboardStore.getState().dataError).toContain('Connect an AWS account')
  })

  it('handles graceful fallback summary when backend summary fails but nodes/spend succeed', async () => {
    useDashboardStore.setState({
      connectionReady: true,
      connectionState: { connected: true, status: 'success', message: '' },
    })

    const mockFetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/dashboard/summary')) {
        return Promise.reject(new Error('Summary API down'))
      }
      if (url.includes('/api/nodes')) {
        return Promise.resolve([
          { instance_id: 'i-1', state: 'running' },
          { instance_id: 'i-2', state: 'stopped' },
        ])
      }
      if (url.includes('/api/spend')) {
        return Promise.resolve([{ date: '2026-03-20', aws: 150.0 }])
      }
      return Promise.resolve([])
    })

    // Mock global fetch
    global.fetch = vi.fn().mockImplementation((url: string) => {
      return mockFetch(url).then(
        (data: any) => ({
          ok: true,
          json: () => Promise.resolve(data),
        }),
        (err: any) => ({
          ok: false,
          json: () => Promise.resolve({ detail: err.message }),
        })
      )
    }) as any

    const apiUrl = (path: string) => `http://localhost:8000${path}`
    await useDashboardStore.getState().fetchData(apiUrl, true)

    const summary = useDashboardStore.getState().summary
    expect(summary).not.toBeNull()
    expect(summary?.total_nodes).toBe(2)
    expect(summary?.running_nodes).toBe(1)
    expect(summary?.partial).toBe(true)

    const dataSources = useDashboardStore.getState().dataSources
    expect(dataSources['summary']?.status).toBe('partial')
    expect(dataSources['nodes']?.status).toBe('ready')
  })

  it('toggles autoRefresh and updates state properly', () => {
    useDashboardStore.setState({ autoRefresh: false })
    const { toggleAutoRefresh, setAutoRefresh } = useDashboardStore.getState()

    toggleAutoRefresh()
    expect(useDashboardStore.getState().autoRefresh).toBe(true)

    toggleAutoRefresh()
    expect(useDashboardStore.getState().autoRefresh).toBe(false)

    setAutoRefresh(true)
    expect(useDashboardStore.getState().autoRefresh).toBe(true)
  })

  it('clears connection state and data when disconnectAccount is called', () => {
    useDashboardStore.setState({
      connectionReady: true,
      connectionState: { connected: true, status: 'success', message: 'Connected' },
      nodes: [{ instance_id: 'i-123', state: 'running' } as any],
    })

    const { disconnectAccount } = useDashboardStore.getState()
    disconnectAccount()

    expect(useDashboardStore.getState().connectionState.connected).toBe(false)
    expect(useDashboardStore.getState().connectionReady).toBe(false)
    expect(useDashboardStore.getState().nodes).toEqual([])
  })

  it('preserves existing nodes (stale-while-revalidate) if background refresh errors', async () => {
    const existingNodes = [{ instance_id: 'i-preserved-1', state: 'running' } as any]
    useDashboardStore.setState({
      connectionReady: true,
      connectionState: { connected: true, status: 'success', message: 'Connected' },
      nodes: existingNodes,
    })

    // Simulate backend throwing 500 on all endpoints
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: 'Temporary network breakdown' }),
      })
    ) as any

    const apiUrl = (path: string) => `http://localhost:8000${path}`
    await useDashboardStore.getState().fetchData(apiUrl, true)

    // Verify existing nodes were NOT wiped
    expect(useDashboardStore.getState().nodes).toEqual(existingNodes)
  })
})
