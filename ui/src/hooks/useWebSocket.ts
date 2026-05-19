import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(
  url: string,
  onMessage: (data: { type: string; data: unknown }) => void,
) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<number>(0)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      reconnectRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessageRef.current(data)
      } catch {
        // Ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Exponential backoff reconnect
      const delay = Math.min(1000 * Math.pow(2, reconnectRef.current), 30000)
      reconnectRef.current += 1
      setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  return { connected }
}
