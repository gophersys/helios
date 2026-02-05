import { useEffect, useRef, useState } from 'react';
import { io, type Socket } from 'socket.io-client';
import { Play, Square, Trash2, ArrowDown } from 'lucide-react';
import { getToken } from '../../api';

interface LogViewerProps {
  namespace: string;
  pod: string;
  container: string;
}

export function LogViewer({ namespace, pod, container }: LogViewerProps) {
  const [lines, setLines] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    return () => {
      if (socketRef.current) {
        socketRef.current.emit('unsubscribe_logs', { namespace, pod, container });
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [namespace, pod, container]);

  useEffect(() => {
    if (autoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines]);

  const startStream = () => {
    const token = getToken();
    if (!token) {
      setError('Not authenticated — please log in again');
      return;
    }

    setError(null);
    setLines([]);
    setConnecting(true);

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:9001';
    const socket = io(`${apiBase}/system`, {
      transports: ['websocket'],
      reconnection: false,
      auth: { token },
    });

    socket.on('connect', () => {
      setConnecting(false);
      setStreaming(true);
      socket.emit('subscribe_logs', {
        namespace,
        pod,
        container,
        tailLines: 200,
      });
    });

    socket.on('log_line', (data: { line: string }) => {
      setLines((prev) => {
        const next = [...prev, data.line];
        return next.length > 5000 ? next.slice(-5000) : next;
      });
    });

    socket.on('log_error', (data: { message: string }) => {
      setError(data.message);
      setStreaming(false);
      setConnecting(false);
    });

    socket.on('connect_error', (err) => {
      setError(`Connection failed: ${err.message}`);
      setStreaming(false);
      setConnecting(false);
      socket.disconnect();
    });

    socket.on('disconnect', () => {
      setStreaming(false);
      setConnecting(false);
    });

    socketRef.current = socket;
  };

  const stopStream = () => {
    if (socketRef.current) {
      socketRef.current.emit('unsubscribe_logs', { namespace, pod, container });
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setStreaming(false);
    setConnecting(false);
  };

  const clearLogs = () => {
    setLines([]);
  };

  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  };

  const handleScroll = () => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      autoScrollRef.current = scrollHeight - scrollTop - clientHeight < 50;
    }
  };

  const isActive = streaming || connecting;

  return (
    <div className="flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 rounded-t-lg border border-b-0 border-border bg-surface-2 px-3 py-2">
        {!isActive ? (
          <button
            onClick={startStream}
            aria-label="Start log stream"
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-success transition-colors hover:bg-surface-1"
          >
            <Play size={12} />
            Stream
          </button>
        ) : (
          <button
            onClick={stopStream}
            aria-label="Stop log stream"
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-error transition-colors hover:bg-surface-1"
          >
            <Square size={12} />
            Stop
          </button>
        )}
        <button
          onClick={clearLogs}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-tertiary transition-colors hover:bg-surface-1 hover:text-text-primary"
        >
          <Trash2 size={12} />
          Clear
        </button>
        <button
          onClick={scrollToBottom}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-tertiary transition-colors hover:bg-surface-1 hover:text-text-primary"
        >
          <ArrowDown size={12} />
          Bottom
        </button>
        <span className="ml-auto text-2xs text-text-tertiary">
          {connecting ? 'Connecting...' : `${lines.length} lines`}
        </span>
      </div>

      {/* Log output */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-96 overflow-auto rounded-b-lg border border-border bg-surface-0 p-3 font-mono text-xs leading-5 text-success"
      >
        {error && (
          <div className="mb-2 text-error">{error}</div>
        )}
        {connecting && (
          <div className="text-text-tertiary">Connecting to {pod}/{container}...</div>
        )}
        {lines.length === 0 && !streaming && !connecting && !error && (
          <div className="text-text-tertiary">Click &quot;Stream&quot; to start viewing logs</div>
        )}
        {/* key={i} is intentional: log lines are append-only with no stable ID */}
        {lines.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap break-all hover:bg-surface-1">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
