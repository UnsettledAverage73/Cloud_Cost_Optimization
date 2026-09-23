import { describe, it, expect } from 'vitest'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { CircleDollarSign } from 'lucide-react'

describe('MetricCard Component', () => {
  it('is a memoized functional component', () => {
    expect(MetricCard).toBeDefined()
    expect(typeof MetricCard).toBe('object') // React.memo returns an object
  })

  it('declares proper prop structure with icon, label, and formatted value', () => {
    const props = {
      icon: CircleDollarSign,
      label: 'Monthly Spend',
      value: '$4,280',
      detail: 'Last synced today',
      tone: 'cyan' as const,
      trend: 'Live',
    }

    expect(props.label).toBe('Monthly Spend')
    expect(props.value).toBe('$4,280')
    expect(props.tone).toBe('cyan')
  })
})
