import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const assetId = searchParams.get('asset_id')
  const category = searchParams.get('category')

  let query = supabase.from('asset_tags').select('*')
  if (assetId) query = query.eq('asset_id', assetId)
  if (category) query = query.eq('taxonomy_category', category)

  const { data, error } = await query
  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}

export async function POST(request: Request) {
  const body = await request.json()
  const { data, error } = await supabase
    .from('asset_tags')
    .insert(body)
    .select()
  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}
