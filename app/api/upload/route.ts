import { supabase } from '@/lib/supabase'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const formData = await request.formData()
  const file = formData.get('file') as File
  const brandId = formData.get('brand_id') as string

  if (!file) return NextResponse.json({ error: 'No file' }, { status: 400 })

  const fileName = `${Date.now()}-${file.name}`
  const { data: uploadData, error: uploadError } = await supabase.storage
    .from('assets')
    .upload(fileName, file)

  if (uploadError) return NextResponse.json({ error: uploadError }, { status: 500 })

  const { data: { publicUrl } } = supabase.storage
    .from('assets')
    .getPublicUrl(fileName)

  const { data, error } = await supabase
    .from('assets')
    .insert({
      title: file.name,
      file_url: publicUrl,
      file_type: file.type,
      brand_id: brandId || null,
      status: 'draft'
    })
    .select()

  if (error) return NextResponse.json({ error }, { status: 500 })
  return NextResponse.json(data)
}
