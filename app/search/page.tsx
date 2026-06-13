'use client'
import { useState } from 'react'
import { api } from '@/lib/api'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function handleSearch() {
    if (!query) return
    setLoading(true)
    try {
      const data = await api.get(`/api/v1/assets/search?q=${encodeURIComponent(query)}`)
      setResults(data)
    } catch (err: any) {
      setResults({ error: err.message || err })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '40px', fontFamily: 'sans-serif' }}>
      <h1>Search Assets</h1>
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search by title..."
        style={{ padding: '8px', width: '300px', marginRight: '10px' }}
      />
      <button onClick={handleSearch} style={{ padding: '8px 16px' }}>
        Search
      </button>

      {loading && <p>Searching...</p>}

      {results && (
        <pre style={{ marginTop: '20px', background: '#f5f5f5', padding: '10px' }}>
          {JSON.stringify(results, null, 2)}
        </pre>
      )}
    </div>
  )
}

