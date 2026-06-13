'use client'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState('')
  const [brandId, setBrandId] = useState<number | null>(null)

  useEffect(() => {
    async function loadBrands() {
      try {
        const brands = await api.get('/api/v1/brands')
        if (brands && brands.length > 0) {
          setBrandId(brands[0].id)
        } else {
          setBrandId(1) // Fallback if no brands exist
        }
      } catch (err) {
        setBrandId(1) // Fallback on error or unauthenticated local dev
      }
    }
    loadBrands()
  }, [])

  async function handleUpload() {
    if (!file || !brandId) {
      setStatus('Please select a file and wait for brand initialization.')
      return
    }
    setStatus('Requesting upload URL...')
    try {
      // Step 1: Generate pre-signed upload parameters
      const uploadParams = await api.post('/api/v1/assets/upload-url', {
        filename: file.name,
        brand_id: brandId,
        asset_type: 'image'
      })

      setStatus('Uploading raw file bytes...')
      // Step 2: Upload raw file bytes via fetch
      const uploadRes = await fetch(uploadParams.upload_url, {
        method: uploadParams.method,
        headers: uploadParams.headers,
        body: file
      })

      if (!uploadRes.ok) {
        throw new Error(`Upload failed with status ${uploadRes.status}`)
      }

      setStatus('Confirming upload and processing metadata...')
      // Step 3: Confirm upload to FastAPI backend
      const confirmData = await api.post('/api/v1/assets/confirm', {
        asset_id: uploadParams.asset_id
      })

      setStatus(`Success! Asset ID: ${confirmData.asset.id} - Status: ${confirmData.asset.status}`)
    } catch (error: any) {
      setStatus(`Error: ${error.message || error}`)
    }
  }

  return (
    <div style={{ padding: '40px', fontFamily: 'sans-serif' }}>
      <h1>Upload Asset (FastAPI Gateway)</h1>
      <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
      <br /><br />
      <button onClick={handleUpload}>Upload</button>
      <p>{status}</p>
    </div>
  )
}

