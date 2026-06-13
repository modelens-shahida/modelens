import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const query = searchParams.get('q')
  const brandId = searchParams.get('brand_id')

  if (!query) return NextResponse.json({ error: 'No query' }, { status: 400 })

  let dbQuery = supabase
    .from('assets')
    .select('*, asset_tags(*)')
    .ilike('title', `%${query}%`)

  if (brandId) dbQuery = dbQuery.eq('brand_id', brandId)

  const { data, error } = await dbQuery

  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}
