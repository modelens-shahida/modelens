import { qdrant, COLLECTIONS } from '@/lib/qdrant'
import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const { query = 'fashion editorial luxury' } = await request.json()
  const results: any = {}

  // Text Search benchmark
  const textStart = Date.now()
  await supabase.from('assets').select('*').ilike('title', `%${query}%`).limit(10)
  results.text_search_ms = Date.now() - textStart

  // Qdrant stats
  const collections = await qdrant.getCollections()
  const stats: any = {}
  for (const col of collections.collections) {
    const info = await qdrant.getCollection(col.name)
    stats[col.name] = { points: info.points_count, status: info.status }
  }

  return NextResponse.json({
    query,
    benchmarks: results,
    qdrant_stats: stats,
    note: 'OpenAI quota exceeded — vector search benchmarks skipped'
  })
}
