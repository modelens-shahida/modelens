import { qdrant, COLLECTIONS } from '@/lib/qdrant'
import { NextResponse } from 'next/server'
import OpenAI from 'openai'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
})

export async function POST(request: Request) {
  const { query, brand_id, limit = 10 } = await request.json()

  if (!query) return NextResponse.json({ error: 'No query' }, { status: 400 })

  let embedding
  try {
    const embeddingResponse = await openai.embeddings.create({
      model: 'text-embedding-3-large',
      input: query
    })
    embedding = embeddingResponse.data[0].embedding
  } catch (e: any) {
    return NextResponse.json({
      error: 'Embedding generation failed',
      details: e?.message || String(e),
      hint: 'Check OpenAI API key and billing/quota'
    }, { status: 502 })
  }

  const filter = brand_id ? {
    must: [{ key: 'brand_id', match: { value: brand_id } }]
  } : undefined

  try {
    const results = await qdrant.search(COLLECTIONS.ASSETS, {
      vector: embedding,
      limit,
      filter,
      with_payload: true
    })

    return NextResponse.json({
      results: results.map(r => ({ ...r.payload, score: r.score })),
      total: results.length
    })
  } catch (e: any) {
    return NextResponse.json({
      error: 'Qdrant search failed',
      details: e?.message || String(e)
    }, { status: 502 })
  }
}
