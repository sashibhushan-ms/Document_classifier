import { useState, useRef } from 'react'
import './App.css'
import './styles/adobe-theme.css'

function App() {
  const [reportData, setReportData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasScanned, setHasScanned] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const folderInputRef = useRef(null)
  const fileInputRef = useRef(null)

  const handleClear = async (type) => {
    if (!confirm(`Are you sure you want to clear all ${type === 'error' ? 'Formula Error' : 'Clean'} files?`)) {
      return
    }
    setLoading(true)
    try {
      const response = await fetch('http://localhost:5000/api/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type }),
      })
      const data = await response.json()
      if (response.ok) {
        alert(data.message)
      } else {
        alert(`Error: ${data.error}`)
      }
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const [progress, setProgress] = useState({ current: 0, total: 0, status: 'idle' })

  const processFiles = async (files) => {
    if (!files || files.length === 0) return

    setLoading(true)
    setError(null)
    setHasScanned(false)
    setReportData([])
    setProgress({ current: 0, total: files.length, status: 'uploading' })

    try {
      // 1. Start Session
      await fetch('http://localhost:5000/api/session/start', { method: 'POST' })

      // 2. Chunk Upload
      const CHUNK_SIZE = 50
      const totalFiles = files.length
      let uploadedCount = 0

      for (let i = 0; i < totalFiles; i += CHUNK_SIZE) {
        const chunk = Array.from(files).slice(i, i + CHUNK_SIZE)
        const formData = new FormData()
        chunk.forEach(file => formData.append('files', file))

        const res = await fetch('http://localhost:5000/api/upload_chunk', {
          method: 'POST',
          body: formData,
        })

        if (!res.ok) {
          const text = await res.text()
          throw new Error(`Upload failed at chunk ${i}: ${text}`)
        }

        uploadedCount += chunk.length
        setProgress({
          current: uploadedCount,
          total: totalFiles,
          status: 'uploading'
        })
      }

      // 3. Start Scan trigger
      const startRes = await fetch('http://localhost:5000/api/scan_start', { method: 'POST' })
      if (!startRes.ok) throw new Error("Failed to start scan")

      // 4. Start polling
      startPolling()

    } catch (err) {
      console.error(err)
      setError(err.message)
      setLoading(false)
    }
  }

  const handleFileSelect = (event) => {
    processFiles(event.target.files)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    setIsDragging(false)

    const items = e.dataTransfer.items
    if (!items || items.length === 0) return

    const allFiles = []

    // Helper to read all files from a directory entry recursively
    const readDirectory = (dirEntry) => {
      return new Promise((resolve) => {
        const reader = dirEntry.createReader()
        const entries = []

        const readEntries = () => {
          reader.readEntries((batch) => {
            if (batch.length === 0) {
              resolve(entries)
            } else {
              entries.push(...batch)
              readEntries()
            }
          })
        }
        readEntries()
      })
    }

    // Helper to get File from FileEntry
    const getFile = (fileEntry) => {
      return new Promise((resolve) => {
        fileEntry.file(resolve)
      })
    }

    // Recursive function to process entries
    const processEntry = async (entry) => {
      if (entry.isFile) {
        const file = await getFile(entry)
        allFiles.push(file)
      } else if (entry.isDirectory) {
        const entries = await readDirectory(entry)
        for (const subEntry of entries) {
          await processEntry(subEntry)
        }
      }
    }

    // Process all dropped items
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry()
      if (entry) {
        await processEntry(entry)
      }
    }

    if (allFiles.length > 0) {
      processFiles(allFiles)
    }
  }

  const startPolling = () => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:5000/api/status')
        const data = await res.json()

        setProgress({
          current: data.progress,
          total: data.total,
          status: data.status
        })

        if (data.status === 'completed') {
          clearInterval(interval)
          await fetchReport()
          setHasScanned(true)
          setLoading(false)
        } else if (data.status === 'error') {
          clearInterval(interval)
          setError(data.message)
          setLoading(false)
        }
      } catch (e) {
        console.error("Polling error", e)
      }
    }, 1000)
  }

  const fetchReport = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/report')
      if (!response.ok) {
        const errText = await response.text()
        throw new Error(`Server Error (${response.status}): ${errText}`)
      }
      const data = await response.json()
      setReportData(data)
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  const handleDownload = (type) => {
    setDownloading(true)
    // Use window.open for large file downloads - more reliable than fetch
    const downloadWindow = window.open(`http://localhost:5000/api/download/${type}`, '_blank')

    // Hide toast after a delay (download starts immediately)
    setTimeout(() => {
      setDownloading(false)
    }, 3000)
  }

  // Calculate stats
  const totalFiles = reportData.length
  const errorFiles = reportData.filter(item => item.label === 'formula_error').length
  const cleanFiles = reportData.filter(item => item.label === 'no_error').length
  const skippedFiles = reportData.filter(item => item.label === 'skipped').length

  return (
    <div className="adobe-page-bg">
      <nav className="adobe-nav">
        <div className="nav-logo">
          <span className="logo-icon">TARGET</span>
          <span className="logo-text">DOCUMENT CLASSIFIER</span>
        </div>
      </nav>

      {downloading && (
        <div className="download-toast">
          <div className="toast-spinner"></div>
          <span>Please wait, preparing your zip file...</span>
        </div>
      )}

      <div className="main-content">
        {!hasScanned && (
          <div className="adobe-hero-card">
            <div className="hero-header">
              <div className="brand-icon">📄</div>
              <h1>Scan Documents for Errors</h1>
              <p className="hero-sub">Drag and drop files or folders to check for math formula issues.</p>
            </div>

            <div
              className={`adobe-dropzone ${isDragging ? 'active' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="drop-watermark">DROP</div>

              <div className="drop-actions">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  multiple
                  style={{ display: 'none' }}
                />

                <button className="adobe-primary-btn" onClick={() => fileInputRef.current.click()} disabled={loading}>
                  📂 Upload Files
                </button>
              </div>
            </div>

            {loading && (
              <div className="adobe-loading">
                <div className="adobe-spinner"></div>
                <p>{progress.status === 'uploading' ? 'Uploading...' : `Scanning ${progress.current}/${progress.total}`}</p>
                <div className="adobe-progress">
                  <div className="fill" style={{ width: `${(progress.current / progress.total) * 100}%` }}></div>
                </div>
              </div>
            )}
            {error && <p className="adobe-error-msg">{error}</p>}
          </div>
        )}

        {hasScanned && (
          <div className="results-container">
            <div className="results-header">
              <h2>SCAN COMPLETED</h2>
              <button className="adobe-secondary-btn" onClick={() => setHasScanned(false)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" /></svg>
                Scan More
              </button>
            </div>

            <div className="stats-row">
              <div className="adobe-stat-card">
                <span className="stat-label">Total Files</span>
                <span className="stat-value">{totalFiles}</span>
              </div>
              <div className="adobe-stat-card error-card">
                <span className="stat-label">Issues Found</span>
                <span className="stat-value">{errorFiles}</span>
                {errorFiles > 0 && (
                  <div className="card-actions">
                    <button className="download-btn" onClick={() => handleDownload('error')}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
                      Download
                    </button>
                  </div>
                )}
              </div>
              <div className="adobe-stat-card success-card">
                <span className="stat-label">Clean Files</span>
                <span className="stat-value">{cleanFiles}</span>
                {cleanFiles > 0 && (
                  <div className="card-actions">
                    <button className="download-btn" onClick={() => handleDownload('clean')}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
                      Download
                    </button>
                  </div>
                )}
              </div>
              <div className="adobe-stat-card skipped-card">
                <span className="stat-label">Skipped Files</span>
                <span className="stat-value">{skippedFiles}</span>
              </div>
            </div>

            <div className="adobe-table-card">
              <table>
                <thead>
                  <tr>
                    <th>File Name</th>
                    <th>Status</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {reportData.map((item, index) => (
                    <tr key={index}>
                      <td className="file-name-cell">{item.input_path.split(/[\\/]/).pop()}</td>
                      <td>
                        <span className={`adobe-badge ${item.label}`}>
                          {item.label === 'formula_error' ? 'Error' : (item.label === 'skipped' ? 'Skipped' : 'Clean')}
                        </span>
                      </td>
                      <td className="details-cell">
                        {item.matches && item.matches.length > 0 ? (
                          <div className="match-count">{item.matches.length} issues found</div>
                        ) : (
                          <span className="nice-text">No issues</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
