import type { Currency } from '@/types/dashboard'

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '')
  }
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    const port = window.location.port
    if ((host === 'localhost' || host === '127.0.0.1') && port !== '8000') {
      return `http://${host}:8000`
    }
  }
  return ''
}

export const apiUrl = (path: string) => {
  if (path.startsWith('http')) return path
  const base = getApiBase()
  return `${base}${path}`
}

export function formatCurrency(
  value: number | null | undefined,
  curr: Currency = 'USD',
  rate = 84.0
): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return curr === 'INR' ? '₹0' : '$0'
  if (curr === 'INR') {
    const inrVal = value * rate
    if (inrVal >= 10_000_000) {
      return `₹${(inrVal / 10_000_000).toFixed(2)} Cr`
    }
    if (inrVal >= 100_000) {
      return `₹${(inrVal / 100_000).toFixed(2)} L`
    }
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(inrVal)
  }
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatInteger(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0'
  return new Intl.NumberFormat('en-US').format(value)
}
