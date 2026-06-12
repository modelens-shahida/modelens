'use client'
import { useState } from 'react'

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState('')

  async function handleUpload() {
    if (!file) return
    setStatus('Uploading...')
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    })
    const data = await res.json()
    if (data[0]?.id) {
      setStatus('Upload successful!')
    } else {
      setStatus('Error: ' + JSON.stringify(data))
    }
  }

  return (
    <div style={{ padding: '40px' }}>
      <h1>Upload Asset</h1>
      <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
      <br /><br />
      <button onClick={handleUpload}>Upload</button>
      <p>{status}</p>
    </div>
  )
}
