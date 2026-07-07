import { NextResponse } from 'next/server'

// Sets the access token as an HTTP-only cookie after FastAPI login/register
export async function POST(request: Request) {
  const { access_token, refresh_token } = await request.json()

  if (!access_token) {
    return NextResponse.json({ error: 'No access_token provided' }, { status: 400 })
  }

  const response = NextResponse.json({ success: true })


  response.cookies.set('modelens_access_token', access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60, // 1 hour, aligns with FastAPI access token expiry
  })


  if (refresh_token) {
    response.cookies.set('modelens_refresh_token', refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 30, // 30 days
    })
  }

  return response
}

// Clears session cookies on logout
export async function DELETE() {
  const response = NextResponse.json({ success: true })
  response.cookies.delete('modelens_access_token')
  response.cookies.delete('modelens_refresh_token')
  return response
}






