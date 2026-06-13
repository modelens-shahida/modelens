import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const { query, brand_id, limit = 10 } = await request.json()

  if (!query) return NextResponse.json({ error: 'No query' }, { status: 400 })

  let textQuery = supabase
    .from('assets')
    .select('*, asset_tags(*)')
    .ilike('title', `%${query}%`)

  if (brand_id) textQuery = textQuery.eq('brand_id', brand_id)

  const { data, error } = await textQuery.limit(limit)

  if (error) return NextResponse.json({ error }, { status: 500 })

  return NextResponse.json({ results: data, total: data?.length })
}
