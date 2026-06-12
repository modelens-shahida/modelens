import { NextResponse } from 'next/server'

const TAXONOMY_SCHEMA = {
  lighting: [
    'natural-daylight', 'golden-hour', 'blue-hour', 'soft-studio',
    'hard-studio', 'backlit', 'rim-light', 'low-key', 'high-key', 'neon'
  ],
  camera: [
    'wide-angle', 'standard', 'portrait-lens', 'telephoto',
    'macro', 'drone', 'overhead', 'eye-level', 'low-angle', 'high-angle'
  ],
  mood: [
    'aspirational', 'playful', 'editorial', 'minimal', 'romantic',
    'bold', 'nostalgic', 'raw', 'serene', 'dramatic'
  ],
  location: [
    'studio', 'urban-street', 'urban-rooftop', 'interior-home',
    'interior-hotel', 'nature-forest', 'nature-beach', 'nature-desert'
  ],
  pose: [
    'standing-front', 'standing-side', 'walking', 'sitting-casual',
    'lying-down', 'candid-motion', 'close-up-face'
  ],
  character: [
    'single-subject', 'duo', 'group', 'model-female', 'model-male',
    'adult-young', 'adult-mid', 'adult-senior'
  ],
  garment: [
    'casual-daywear', 'smart-casual', 'formal-wear', 'activewear',
    'swimwear', 'outerwear', 'eveningwear', 'streetwear'
  ],
  campaign: [
    'hero-shot', 'supporting', 'social-cutdown', 'product-focus',
    'lifestyle', 'behind-the-scenes'
  ]
}

export async function GET() {
  return NextResponse.json({
    version: '1.0',
    categories: Object.keys(TAXONOMY_SCHEMA).length,
    schema: TAXONOMY_SCHEMA
  })
}
