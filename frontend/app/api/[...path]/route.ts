import { NextRequest, NextResponse } from 'next/server'

const rawBackend = process.env.BACKEND_URL || 'http://127.0.0.1:8000'
const backendUrl = rawBackend.startsWith('http://') || rawBackend.startsWith('https://')
  ? rawBackend.replace(/\/$/, '')
  : `https://${rawBackend.replace(/\/$/, '')}`

function buildTarget(path: string[], search: string) {
  return `${backendUrl}/api/${path.join('/')}${search}`
}

async function proxy(request: NextRequest, params: Promise<{ path: string[] }>) {
  const { path = [] } = await params
  const target = buildTarget(path, new URL(request.url).search)

  try {
    const headers = new Headers(request.headers)
    headers.delete('host')

    const method = request.method.toUpperCase()
    const init: RequestInit = { method, headers }

    if (method !== 'GET' && method !== 'HEAD') {
      init.body = await request.text()
    }

    const upstream = await fetch(target, init)
    const contentType = upstream.headers.get('content-type') || 'application/json; charset=utf-8'
    const body = await upstream.text()

    return new Response(body, {
      status: upstream.status,
      headers: {
        'content-type': contentType,
      },
    })
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unknown proxy failure'
    return NextResponse.json(
      {
        error: 'Backend unavailable',
        detail,
        target,
      },
      { status: 503 }
    )
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context.params)
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context.params)
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context.params)
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context.params)
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context.params)
}
