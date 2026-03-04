import { useMemo, useRef, useState } from 'react'

const BACKEND_HTTP_URL = import.meta.env.VITE_BACKEND_HTTP_URL || 'http://localhost:8000'
const BACKEND_WS_URL = import.meta.env.VITE_BACKEND_WS_URL || 'ws://localhost:8000/query'

export default function App() {
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState('')
  const [citations, setCitations] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [connectionState, setConnectionState] = useState('idle')
  const [error, setError] = useState('')

  const [selectedFile, setSelectedFile] = useState(null)
  const [uploadState, setUploadState] = useState('idle')
  const [uploadMessage, setUploadMessage] = useState('')

  const wsRef = useRef(null)

  const citationKey = (item) => `${item?.source || 'unknown'}-${item?.chunk_id ?? 0}`

  const uniqueCitations = useMemo(() => {
    const map = new Map()
    for (const item of citations) {
      map.set(citationKey(item), item)
    }
    return Array.from(map.values())
  }, [citations])

  const cleanupSocket = () => {
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onerror = null
      wsRef.current.onclose = null
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close()
      }
      wsRef.current = null
    }
  }

  const handleAsk = async (event) => {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || isStreaming) return

    setError('')
    setResponse('')
    setCitations([])
    setIsStreaming(true)
    setConnectionState('connecting')

    cleanupSocket()

    const ws = new WebSocket(BACKEND_WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionState('connected')
      ws.send(trimmed)
    }

    ws.onmessage = (eventMessage) => {
      try {
        const data = JSON.parse(eventMessage.data)

        if (data.type === 'token') {
          setResponse((prev) => prev + (data.payload || ''))
          if (Array.isArray(data.citations) && data.citations.length > 0) {
            setCitations((prev) => [...prev, ...data.citations])
          }
          return
        }

        if (data.type === 'citation') {
          const citationPayload = data.payload
          if (citationPayload && typeof citationPayload === 'object') {
            setCitations((prev) => [...prev, citationPayload])
          }
          if (Array.isArray(data.citations) && data.citations.length > 0) {
            setCitations((prev) => [...prev, ...data.citations])
          }
          return
        }

        if (data.type === 'error') {
          const message = typeof data.payload === 'string'
            ? data.payload
            : data.payload?.message || 'Unknown streaming error'
          setError(message)
          setIsStreaming(false)
          setConnectionState('error')
          cleanupSocket()
          return
        }

        if (data.type === 'complete') {
          setIsStreaming(false)
          setConnectionState('completed')
          cleanupSocket()
        }
      } catch {
        setError('Invalid message received from server')
        setIsStreaming(false)
        setConnectionState('error')
        cleanupSocket()
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection failed')
      setIsStreaming(false)
      setConnectionState('error')
      cleanupSocket()
    }

    ws.onclose = () => {
      if (isStreaming) {
        setIsStreaming(false)
        setConnectionState((prev) => (prev === 'error' ? prev : 'closed'))
      }
    }
  }

  const handleFileUpload = async (event) => {
    event.preventDefault()
    if (!selectedFile || uploadState === 'uploading') return

    setUploadState('uploading')
    setUploadMessage('Uploading document...')

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await fetch(`${BACKEND_HTTP_URL}/ingest`, {
        method: 'POST',
        body: formData,
      })

      const result = await response.json()

      if (!response.ok) {
        setUploadState('error')
        setUploadMessage(result?.detail || 'Upload failed')
        return
      }

      setUploadState('success')
      setUploadMessage(result?.message || 'Document ingestion initiated')
    } catch {
      setUploadState('error')
      setUploadMessage('Upload failed. Check backend service.')
    }
  }

  return (
    <div className="page">
      <header className="header">
        <h1>Real-Time Streaming RAG</h1>
        <p>FastAPI + Redis + ChromaDB + Ollama</p>
      </header>

      <main className="grid">
        <section className="card">
          <h2>Ask a Question</h2>
          <form onSubmit={handleAsk} className="stack">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question..."
              rows={4}
            />
            <button type="submit" disabled={isStreaming || !query.trim()}>
              {isStreaming ? 'Streaming...' : 'Send Query'}
            </button>
          </form>

          <div className="status">Connection: <strong>{connectionState}</strong></div>
          {error ? <div className="error">{error}</div> : null}

          <div className="response" aria-live="polite">
            {response || 'Response will stream here...'}
          </div>

          <div className="citations">
            <h3>Citations</h3>
            {uniqueCitations.length === 0 ? (
              <p>No citations received yet.</p>
            ) : (
              <ul>
                {uniqueCitations.map((c) => (
                  <li key={citationKey(c)}>
                    <span>{c.source || 'unknown'}</span>
                    <span>chunk: {c.chunk_id ?? 0}</span>
                    <span>score: {typeof c.similarity === 'number' ? c.similarity.toFixed(3) : 'n/a'}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="card">
          <h2>Upload Document</h2>
          <form onSubmit={handleFileUpload} className="stack">
            <input
              type="file"
              accept=".txt,.pdf,.md,.doc,.docx"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            />
            <button type="submit" disabled={!selectedFile || uploadState === 'uploading'}>
              {uploadState === 'uploading' ? 'Uploading...' : 'Upload to /ingest'}
            </button>
          </form>

          <div className={`upload ${uploadState}`}>
            {uploadMessage || 'Choose a file and upload to start ingestion.'}
          </div>

          <div className="help">
            <h3>How to use</h3>
            <ol>
              <li>Upload a document.</li>
              <li>Wait for worker to process embeddings.</li>
              <li>Ask a question and watch tokens stream live.</li>
            </ol>
          </div>
        </section>
      </main>
    </div>
  )
}
