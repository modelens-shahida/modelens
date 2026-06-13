import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function GET() {
  const { data, error } = await supabase
    .from('brands')
    .select('*')

  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}

export async function POST(request: Request) {
  const body = await request.json()
  const { data, error } = await supabase
    .from('brands')
    .insert(body)
    .select()

  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}
