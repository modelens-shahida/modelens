import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const assetId = searchParams.get('asset_id')

  const { data, error } = await supabase
    .from('assets')
    .select(`
      *,
      asset_tags(*),
      asset_metadata(*)
    `)
    .eq('id', assetId || '')

  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}

export async function PATCH(request: Request) {
  const body = await request.json()
  const { asset_id, campaign_id, character_id, brand_id } = body

  const { data, error } = await supabase
    .from('assets')
    .update({
      campaign_id: campaign_id || null,
      brand_id: brand_id || null,
    })
    .eq('id', asset_id)
    .select()

  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}
