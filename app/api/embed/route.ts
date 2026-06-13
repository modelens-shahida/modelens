import { supabase } from '@/lib/supabase'
import { qdrant, COLLECTIONS } from '@/lib/qdrant'
import { NextResponse } from 'next/server'
import OpenAI from 'openai'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
})

export async function POST(request: Request) {
  const { asset_id } = await request.json()

  if (!asset_id) return NextResponse.json({ error: 'No asset_id' }, { status: 400 })

  const { data: asset, error } = await supabase
    .from('assets')
    .select('*, asset_tags(*)')
    .eq('id', asset_id)
    .single()

  if (error || !asset) return NextResponse.json({ error: 'Asset not found' }, { status: 404 })

  const text = `${asset.title || ''} ${asset.file_type || ''} ${
    asset.asset_tags?.map((t: any) => t.tag_value).join(' ') || ''
  }`

  let embedding
  try {
    const embeddingResponse = await openai.embeddings.create({
      model: 'text-embedding-3-large',
      input: text
    })
    embedding = embeddingResponse.data[0].embedding
  } catch (e: any) {
    return NextResponse.json({
      error: 'Embedding generation failed',
      details: e?.message || String(e),
      hint: 'Check OpenAI API key and billing/quota'
    }, { status: 502 })
  }

  try {
    await qdrant.upsert(COLLECTIONS.ASSETS, {
      points: [{
        id: asset_id,
        vector: embedding,
        payload: {
          asset_id,
          brand_id: asset.brand_id,
          title: asset.title,
          file_type: asset.file_type,
          status: asset.status
        }
      }]
    })
    return NextResponse.json({ success: true, asset_id })
  } catch (e: any) {
    return NextResponse.json({
      error: 'Qdrant upsert failed',
      details: e?.message || String(e)
    }, { status: 502 })
  }
}
