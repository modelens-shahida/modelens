import { QdrantClient } from '@qdrant/js-client-rest'

export const qdrant = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY
})

export const COLLECTIONS = {
  ASSETS: 'assets',
  PROMPTS: 'prompts',
  CHARACTERS: 'characters',
  BRAND_MEMORY: 'brand_memory',
  CAMPAIGN_MEMORY: 'campaign_memory'
}

export async function initCollections() {
  const collections = Object.values(COLLECTIONS)
  
  for (const name of collections) {
    const existing = await qdrant.getCollections()
    const exists = existing.collections.find(c => c.name === name)
    
    if (!exists) {
      await qdrant.createCollection(name, {
        vectors: {
          size: 1536,
          distance: 'Cosine'
        }
      })
      console.log(`Collection created: ${name}`)
    }
  }
}
