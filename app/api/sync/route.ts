import { supabase } from '@/lib/supabase'
import { qdrant, COLLECTIONS } from '@/lib/qdrant'
import { NextResponse } from 'next/server'
import OpenAI from 'openai'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
})

export async function POST() {
  try {
    // Supabase se saare assets fetch karo
    const { data: assets, error } = await supabase
      .from('assets')
      .select('*, asset_tags(*)')

    if (error) return NextResponse.json({ error }, { status: 500 })

    let synced = 0
    let failed = 0

    for (const asset of assets || []) {
      try {
        // Text banao embedding ke liye
        const text = `${asset.title || ''} ${asset.file_type || ''} ${
          asset.asset_tags?.map((t: any) => t.tag_value).join(' ') || ''
        }`

        // Embedding generate karo
        const embeddingResponse = await openai.embeddings.create({
          model: 'text-embedding-3-large',
          input: text
        })
        const embedding = embeddingResponse.data[0].embedding

        // Qdrant mein upsert karo
        await qdrant.upsert(COLLECTIONS.ASSETS, {
          points: [{
            id: asset.id,
            vector: embedding,
            payload: {
              asset_id: asset.id,
              brand_id: asset.brand_id,
              title: asset.title,
              file_type: asset.file_type,
              status: asset.status
            }
          }]
        })
        synced++
      } catch (e) {
        failed++
        console.error(`Failed to sync asset ${asset.id}:`, e)
      }
    }

    return NextResponse.json({
      success: true,
      total: assets?.length,
      synced,
      failed
    })
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}

export async function GET() {
  try {
    const collections = await qdrant.getCollections()
    const stats: any = {}

    for (const col of collections.collections) {
      const info = await qdrant.getCollection(col.name)
      stats[col.name] = {
        points: info.points_count,
        status: info.status
      }
    }

    return NextResponse.json({ stats })
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
