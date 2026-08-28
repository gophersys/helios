# Phase 5 — Frontend: Terminal Component + Pod Exec Integration

## Objective

Build a terminal component using xterm.js and integrate it into the pod detail page. Super admins can exec into running containers with an interactive shell.

---

## 1. Create `src/app/components/system/terminal.tsx`

```tsx
import { useEffect, useRef, useState } from 'react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { io, type Socket } from 'socket.io-client';
import { TerminalSquare, X } from 'lucide-react';
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

    // Create terminal
    const term = new XTerminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
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

    // Connect to server
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:9001';
    const socket = io(`${apiBase}/system`, {
      transports: ['websocket'],
      auth: {
        token: localStorage.getItem('token') || '',
      },
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

    socket.on('disconnect', () => {
      setConnected(false);
      term.writeln('\x1b[31mDisconnected\x1b[0m');
    });

    // Forward input to server
    term.onData((data) => {
      if (socket.connected) {
        socket.emit('exec_input', { data });
      }
    });

    // Handle resize
    const handleResize = () => {
      fitAddon.fit();
      if (socket.connected) {
        socket.emit('exec_resize', {
          cols: term.cols,
          rows: term.rows,
        });
      }
    };

    term.onResize(({ cols, rows }) => {
      if (socket.connected) {
        socket.emit('exec_resize', { cols, rows });
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
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
      {/* Terminal header */}
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
        >
          <X size={14} />
        </button>
      </div>

      {/* Terminal body */}
      <div ref={termRef} className="h-80 bg-[#1a1a2e]" />

      {error && (
        <div className="border-t border-border bg-error/10 px-3 py-1.5 text-xs text-error">
          {error}
        </div>
      )}
    </div>
  );
}
```

---

## 2. Add xterm.css to the build

The `@xterm/xterm/css/xterm.css` import in the component should work with Vite's CSS handling. If it doesn't, add to `index.html` or import in the component's parent.

---

## 3. Modify `src/app/pages/system/pod-detail.tsx`

Add the exec button and terminal to the pod detail page.

**Add import:**

```tsx
import { Terminal } from '../../components/system/terminal';
import { TerminalSquare } from 'lucide-react';
```

**Add state:**

```tsx
const [showExec, setShowExec] = useState(false);
```

**Add exec button** next to the delete button in the header (System.Manage only):

```tsx
{canManage && pod.status === 'Running' && (
  <button
    onClick={() => setShowExec(!showExec)}
    className="flex items-center gap-1.5 rounded bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:bg-surface-3"
  >
    <TerminalSquare size={12} />
    {showExec ? 'Hide Terminal' : 'Exec'}
  </button>
)}
```

**Add terminal section** after the log viewer section:

```tsx
{showExec && selectedContainer && namespace && pod.name && (
  <div className="mb-6">
    <h3 className="mb-2 text-sm font-medium text-text-primary">Terminal</h3>
    <Terminal
      namespace={namespace}
      pod={pod.name}
      container={selectedContainer}
      onClose={() => setShowExec(false)}
    />
  </div>
)}
```

---

## 4. Container selector applies to both logs and exec

The existing `selectedContainer` state in pod-detail.tsx already controls which container the log viewer connects to. The same state should control the terminal. When the user changes the container dropdown, both the log viewer and terminal should update.

If the user switches containers while a terminal is open, close the terminal and reopen it for the new container. Add this effect:

```tsx
// Close terminal when container changes
useEffect(() => {
  setShowExec(false);
}, [selectedContainer]);
```

---

## Verification

1. Frontend compiles without errors
2. xterm.js renders correctly in the terminal div
3. "Exec" button appears only for running pods and System.Manage users
4. Clicking "Exec" opens an interactive terminal
5. Shell commands work (ls, cat, etc.)
6. Terminal resizes correctly when the window is resized
7. Terminal disconnects cleanly when closed
8. Container selector dropdown affects both log viewer and terminal

---

## Overview Update

```
- [x] Phase 5 — Frontend: terminal component + pod exec integration
```
