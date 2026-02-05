import { useEffect, useRef, useState } from 'react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { io, type Socket } from 'socket.io-client';
import { TerminalSquare, X } from 'lucide-react';
import { getToken } from '../../api';
import '@xterm/xterm/css/xterm.css';

interface TerminalProps {
  namespace: string;
  pod: string;
  container: string;
  onClose: () => void;
}

export function Terminal({ namespace, pod, container, onClose }: TerminalProps) {
  const termRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerminal | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!termRef.current) return;

    const term = new XTerminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
      // xterm.js requires hex color values for its theme configuration
      theme: {
        background: '#1a1a2e',
        foreground: '#e0e0e0',
        cursor: '#e0e0e0',
        selectionBackground: '#3a3a5e',
        black: '#1a1a2e',
        red: '#ff6b6b',
        green: '#51cf66',
        yellow: '#ffd43b',
        blue: '#74c0fc',
        magenta: '#da77f2',
        cyan: '#66d9e8',
        white: '#e0e0e0',
      },
      allowProposedApi: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitRef.current = fitAddon;

    const token = getToken();
    if (!token) {
      setError('Not authenticated — please log in again');
      term.writeln('\x1b[31mNot authenticated — please log in again\x1b[0m');
      return;
    }

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:9001';
    const socket = io(`${apiBase}/system`, {
      transports: ['websocket'],
      reconnection: false,
      auth: { token },
    });

    socket.on('connect', () => {
      setConnected(true);
      term.writeln(`\x1b[32mConnecting to ${pod}/${container}...\x1b[0m`);
      socket.emit('exec_start', {
        namespace,
        pod,
        container,
        command: ['/bin/sh'],
      });
    });

    socket.on('exec_output', (data: { data: string }) => {
      term.write(data.data);
    });

    socket.on('exec_error', (data: { message: string }) => {
      setError(data.message);
      term.writeln(`\x1b[31mError: ${data.message}\x1b[0m`);
    });

    socket.on('exec_exit', (data: { code: number }) => {
      term.writeln(`\x1b[33mSession exited with code ${data.code}\x1b[0m`);
      setConnected(false);
    });

    socket.on('connect_error', (err) => {
      setError(`Connection failed: ${err.message}`);
      term.writeln(`\x1b[31mConnection failed: ${err.message}\x1b[0m`);
      setConnected(false);
      socket.disconnect();
    });

    socket.on('disconnect', () => {
      setConnected(false);
      term.writeln('\x1b[31mDisconnected\x1b[0m');
    });

    term.onData((data) => {
      if (socket.connected) {
        socket.emit('exec_input', { data });
      }
    });

    term.onResize(({ cols, rows }) => {
      if (socket.connected) {
        socket.emit('exec_resize', { cols, rows });
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(termRef.current);

    socketRef.current = socket;

    return () => {
      resizeObserver.disconnect();
      socket.emit('exec_stop');
      socket.disconnect();
      term.dispose();
      xtermRef.current = null;
      socketRef.current = null;
      fitRef.current = null;
    };
  }, [namespace, pod, container]);

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border">
      <div className="flex items-center justify-between border-b border-border bg-surface-2 px-3 py-2">
        <div className="flex items-center gap-2">
          <TerminalSquare size={14} className="text-text-tertiary" />
          <span className="text-xs font-medium text-text-primary">
            {pod} / {container}
          </span>
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              connected ? 'bg-success' : 'bg-error'
            }`}
          />
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-text-tertiary transition-colors hover:text-text-primary"
          aria-label="Close terminal"
        >
          <X size={14} />
        </button>
      </div>
      <div ref={termRef} className="h-80 bg-surface-0" />
      {error && (
        <div className="border-t border-border bg-error-muted px-3 py-1.5 text-xs text-error">
          {error}
        </div>
      )}
    </div>
  );
}
