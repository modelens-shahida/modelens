import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('modelens_access_token')?.value

  if (!token) {
    const loginUrl = new URL('/auth/login', request.url)
    // Keep the full intended destination (path + query) for after login
    loginUrl.searchParams.set('redirect', request.nextUrl.pathname + request.nextUrl.search)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: '/dashboard/:path*',
}
