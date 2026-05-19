import { useState, useEffect, useCallback } from 'react'

export function useApi<T>(
  endpoint: string,
  params?: Record<string, string | number | undefined>,
  pollInterval = 2000,
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const searchParams = new URLSearchParams()
      if (params) {
        for (const [key, value] of Object.entries(params)) {
          if (value !== undefined && value !== null) {
            searchParams.set(key, String(value))
          }
        }
      }
      const query = searchParams.toString()
      const url = `/api/${endpoint}${query ? `?${query}` : ''}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [endpoint, params ? JSON.stringify(params) : null])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, pollInterval)
    return () => clearInterval(interval)
  }, [fetchData, pollInterval])

  return { data, loading, error, refresh: fetchData }
}
