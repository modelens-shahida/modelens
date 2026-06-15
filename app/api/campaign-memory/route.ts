import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const campaignId = searchParams.get('campaign_id')

  if (!campaignId) return NextResponse.json({ error: 'No campaign_id' }, { status: 400 })

  const { data: campaignAssets, error } = await supabase
    .from('campaign_assets')
    .select('asset:assets(*, asset_tags(*))')
    .eq('campaign_id', campaignId)

  if (error) return NextResponse.json({ error }, { status: 500 })

  const assets = campaignAssets ? campaignAssets.map((ca: any) => ca.asset).filter(Boolean) : []

  const tags: Record<string, number> = {}
  assets.forEach(asset => {
    asset.asset_tags?.forEach((tag: any) => {
      const key = `${tag.taxonomy_category}:${tag.tag_value}`
      tags[key] = (tags[key] || 0) + 1
    })
  })

  return NextResponse.json({
    campaign_id: campaignId,
    total_assets: assets.length,
    tag_frequency: tags
  })
}
