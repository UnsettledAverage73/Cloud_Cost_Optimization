import { describe, it, expect } from 'vitest'
import { FEATURE_EXPLAINERS } from '@/lib/explainers'
import { FeatureExplainer } from '@/components/ui/feature-explainer'

describe('FeatureExplainer & Explainer Registry', () => {
  it('exports a valid feature explainer component', () => {
    expect(FeatureExplainer).toBeDefined()
    expect(typeof FeatureExplainer).toBe('function')
  })

  it('contains comprehensive feature coverage for all dashboard views and metrics', () => {
    expect(FEATURE_EXPLAINERS['nav-overview']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-inventory']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-telemetry']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-security']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-optimization']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-scheduler']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-gitops-sla']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-fleet']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-cicd']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-copilot']).toBeDefined()
    expect(FEATURE_EXPLAINERS['nav-settings']).toBeDefined()

    expect(FEATURE_EXPLAINERS['metric-total-spend']).toBeDefined()
    expect(FEATURE_EXPLAINERS['metric-active-nodes']).toBeDefined()
    expect(FEATURE_EXPLAINERS['metric-wasted-spend']).toBeDefined()
    expect(FEATURE_EXPLAINERS['metric-security-risks']).toBeDefined()
  })

  it('provides structured title, category, description, and impact for every explainer', () => {
    const keys = Object.keys(FEATURE_EXPLAINERS)
    expect(keys.length).toBeGreaterThanOrEqual(15)

    for (const key of keys) {
      const item = FEATURE_EXPLAINERS[key]
      expect(item.title).toBeTruthy()
      expect(item.category).toMatch(/^(FinOps|Security|Architecture|Performance|Reliability|DevOps)$/)
      expect(item.description.length).toBeGreaterThan(20)
      expect(item.impact.length).toBeGreaterThan(15)
    }
  })
})
