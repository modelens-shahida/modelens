import { qdrant, COLLECTIONS } from '@/lib/qdrant'
import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'
import OpenAI from 'openai'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
})

export async function POST(request: Request) {
  // Step 1 — Validate JWT via Supabase
  const authHeader = request.headers.get('Authorization')
  if (!authHeader) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const token = authHeader.split(' ')[1]
  const { data: { user }, error: authError } = await supabase.auth.getUser(token)

  if (authError || !user) {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
  }

  // Step 2 — Look up the user's brand (ignore any brand_id from the body)
  const { data: userRow, error: userError } = await supabase
    .from('users')
    .select('brand_id')
    .eq('id', user.id)
    .single()

  if (userError || !userRow?.brand_id) {
    return NextResponse.json({ error: 'No brand associated with this user' }, { status: 403 })
  }

  const brand_id = userRow.brand_id

  // Step 3 — Parse request body
  const { query, limit = 10 } = await request.json()
  if (!query) return NextResponse.json({ error: 'No query' }, { status: 400 })

  // Step 4 — Generate embedding
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

  // Step 5 — Search Qdrant, scoped to the user's brand only
  const filter = {
    must: [{ key: 'brand_id', match: { value: brand_id } }]
  }

  try {
    const results = await qdrant.search(COLLECTIONS.ASSETS, {
      vector: embedding,
      limit,
      filter,
      with_payload: true
    })

    return NextResponse.json({
      brand_id,
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
