import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { MonitoringProvider } from '@/components/monitoring-provider'
import { OptimisticToastProvider } from '@/components/ui/optimistic-toast'
import './globals.css'

export const metadata: Metadata = {
  title: 'CloudPulse — Multi-cloud observability',
  description: 'Infrastructure, cost optimization, and telemetry intelligence for every cloud.',
  generator: 'CloudPulse',
  icons: {
    icon: '/icon.svg',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  colorScheme: 'dark light',
  themeColor: '#0b1220',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="bg-background">
      <head>
        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="antialiased">
        <MonitoringProvider>
          <OptimisticToastProvider>
            {children}
          </OptimisticToastProvider>
        </MonitoringProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
