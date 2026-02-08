import { browser } from '$app/environment';
import { io, Socket } from 'socket.io-client';
import { getToken } from '$lib/api';

let systemSocket: Socket | null = null;

export interface LogSubscription {
  namespace: string;
  pod: string;
  container: string;
  tailLines?: number;
}

export interface ExecSession {
  namespace: string;
  pod: string;
  container: string;
  command?: string[];
}

/**
 * Get or create the Socket.IO connection to /system namespace.
 * Authenticates with JWT token.
 */
export function getSystemSocket(): Socket | null {
  if (!browser) return null;

  if (systemSocket?.connected) {
    return systemSocket;
  }

  const token = getToken();
  if (!token) {
    console.warn('No auth token available for WebSocket connection');
    return null;
  }

  // Close existing socket if any
  if (systemSocket) {
    systemSocket.disconnect();
  }

  // Create new socket connection
  systemSocket = io('/system', {
    auth: { token },
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
  });

  systemSocket.on('connect', () => {
    console.log('System WebSocket connected');
  });

  systemSocket.on('connect_error', (err) => {
    console.error('System WebSocket connection error:', err.message);
  });

  systemSocket.on('disconnect', (reason) => {
    console.log('System WebSocket disconnected:', reason);
  });

  return systemSocket;
}

/**
 * Disconnect the system socket.
 */
export function disconnectSystemSocket(): void {
  if (systemSocket) {
    systemSocket.disconnect();
    systemSocket = null;
  }
}

/**
 * Subscribe to pod logs.
 */
export function subscribeLogs(
  subscription: LogSubscription,
  onLine: (line: string) => void,
  onError: (message: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError('WebSocket not available');
    return () => {};
  }

  const lineHandler = (data: { line: string }) => {
    onLine(data.line);
  };

  const errorHandler = (data: { message: string }) => {
    onError(data.message);
  };

  socket.on('log_line', lineHandler);
  socket.on('log_error', errorHandler);

  socket.emit('subscribe_logs', {
    namespace: subscription.namespace,
    pod: subscription.pod,
    container: subscription.container,
    tailLines: subscription.tailLines ?? 100,
  });

  // Return unsubscribe function
  return () => {
    socket.off('log_line', lineHandler);
    socket.off('log_error', errorHandler);
    socket.emit('unsubscribe_logs', {
      namespace: subscription.namespace,
      pod: subscription.pod,
      container: subscription.container,
    });
  };
}

/**
 * Start an exec session.
 */
export function startExec(
  session: ExecSession,
  onOutput: (data: string) => void,
  onExit: (code: number) => void,
  onError: (message: string) => void
): {
  sendInput: (data: string) => void;
  resize: (cols: number, rows: number) => void;
  stop: () => void;
} {
  const socket = getSystemSocket();
  if (!socket) {
    onError('WebSocket not available');
    return {
      sendInput: () => {},
      resize: () => {},
      stop: () => {},
    };
  }

  const outputHandler = (data: { data: string }) => {
    onOutput(data.data);
  };

  const exitHandler = (data: { code: number }) => {
    onExit(data.code);
  };

  const errorHandler = (data: { message: string }) => {
    onError(data.message);
  };

  socket.on('exec_output', outputHandler);
  socket.on('exec_exit', exitHandler);
  socket.on('exec_error', errorHandler);

  socket.emit('exec_start', {
    namespace: session.namespace,
    pod: session.pod,
    container: session.container,
    command: session.command ?? ['/bin/sh'],
  });

  return {
    sendInput: (data: string) => {
      socket.emit('exec_input', { data });
    },
    resize: (cols: number, rows: number) => {
      socket.emit('exec_resize', { cols, rows });
    },
    stop: () => {
      socket.off('exec_output', outputHandler);
      socket.off('exec_exit', exitHandler);
      socket.off('exec_error', errorHandler);
      socket.emit('exec_stop');
    },
  };
}
