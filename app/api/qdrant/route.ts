import { NextResponse } from 'next/server'
import { initCollections, qdrant, COLLECTIONS } from '@/lib/qdrant'

export async function GET() {
  try {
    await initCollections()
    const collections = await qdrant.getCollections()
    return NextResponse.json({ 
      success: true, 
      collections: collections.collections 
    })
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
