<script lang="ts">
  // Svelte imports
  import { onMount, onDestroy } from 'svelte';

  // SvelteKit imports
  import { browser } from '$app/environment';

  // External libraries
  import { X, RefreshCw } from 'lucide-svelte';

  // Internal components
  import Select from '$lib/components/ui/select.svelte';

  // Internal imports
  import { startExec } from '$lib/services/websocket';

  interface Props {
    namespace: string;
    pod: string;
    container: string;
    onclose: () => void;
  }

  let { namespace, pod, container, onclose }: Props = $props();

  let terminalContainer: HTMLDivElement;
  let terminal: any = null;
  let fitAddon: any = null;
  let status = $state<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  let errorMessage = $state<string | null>(null);
  let shell = $state('/bin/sh');
  let inputHandlerDispose: (() => void) | null = null;

  let execSession: {
    sendInput: (data: string) => void;
    resize: (cols: number, rows: number) => void;
    stop: () => void;
  } | null = null;

  let resizeObserver: ResizeObserver | null = null;

  async function initTerminal() {
    if (!browser || !terminalContainer) return;

// Dynamic import xterm (client-side only)
    const { Terminal } = await import('xterm');
    const { FitAddon } = await import('@xterm/addon-fit');
    const { WebLinksAddon } = await import('@xterm/addon-web-links');

    // Import xterm CSS
    await import('xterm/css/xterm.css');

    // Create terminal
    terminal = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      scrollback: 1000,
      theme: {
        background: '#0d1117',
        foreground: '#c9d1d9',
        cursor: '#c9d1d9',
        cursorAccent: '#0d1117',
        selectionBackground: '#3b5070',
        black: '#0d1117',
        red: '#ff7b72',
        green: '#7ee787',
        yellow: '#d29922',
        blue: '#79c0ff',
        magenta: '#d2a8ff',
        cyan: '#a5d6ff',
        white: '#c9d1d9',
        brightBlack: '#484f58',
        brightRed: '#ffa198',
        brightGreen: '#7ee787',
        brightYellow: '#e3b341',
        brightBlue: '#a5d6ff',
        brightMagenta: '#d2a8ff',
        brightCyan: '#a5d6ff',
        brightWhite: '#f0f6fc',
      },
    });

    // Add addons
    fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.loadAddon(new WebLinksAddon());

    // Open terminal in container
    terminal.open(terminalContainer);

    // Fit after a small delay to ensure container has dimensions
    setTimeout(() => {
      fitAddon.fit();
      terminal.focus();
    }, 50);

    // Set up input handler ONCE
    inputHandlerDispose = terminal.onData((data: string) => {
      if (execSession) {
        execSession.sendInput(data);
      }
    });

    // Connect to pod
    connect();

    // Handle resize
    resizeObserver = new ResizeObserver(() => {
      if (fitAddon && terminal) {
        fitAddon.fit();
        if (execSession && status === 'connected') {
          execSession.resize(terminal.cols, terminal.rows);
        }
      }
    });
    resizeObserver.observe(terminalContainer);
  }

  function connect() {
    // Stop existing session if any
    if (execSession) {
      execSession.stop();
      execSession = null;
    }

    status = 'connecting';
    errorMessage = null;

    // Use env to set TERM=xterm for proper terminal support (arrow keys, etc)
    execSession = startExec(
      { namespace, pod, container, command: ['env', 'TERM=xterm', shell] },
      (data) => {
        // Output from container
        if (status !== 'connected') {
          status = 'connected';
          terminal?.focus();
        }
        terminal?.write(data);
      },
      (code) => {
        // Session exited
        status = 'disconnected';
        terminal?.writeln(`\r\n\x1b[33m>>> Session exited with code ${code}\x1b[0m`);
      },
      (message) => {
        // Error
        status = 'error';
        errorMessage = message;
        terminal?.writeln(`\r\n\x1b[31m>>> Error: ${message}\x1b[0m`);
        terminal?.writeln(`\x1b[33m>>> Shell "${shell}" may not exist in this container. Try a different shell.\x1b[0m`);
      }
    );

    // Send initial resize after exec is started
    setTimeout(() => {
      if (terminal && execSession) {
        execSession.resize(terminal.cols || 80, terminal.rows || 24);
        terminal.focus();
      }
    }, 300);
  }

  function reconnect() {
    terminal?.clear();
    connect();
  }

  function handleClose() {
    if (execSession) {
      execSession.stop();
    }
    onclose();
  }

  function focusTerminal() {
    terminal?.focus();
  }

  onMount(() => {
    initTerminal();
  });

  onDestroy(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
    if (inputHandlerDispose) {
      inputHandlerDispose();
    }
    if (execSession) {
      execSession.stop();
    }
    if (terminal) {
      terminal.dispose();
    }
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-modal flex items-center justify-center bg-overlay">
  <div class="w-[90vw] h-[80vh] max-w-6xl bg-surface-1 rounded-lg border border-border flex flex-col shadow-xl overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-0 shrink-0">
      <div class="flex items-center gap-3">
        <h3 class="text-lg font-semibold text-text-primary">Terminal</h3>
        <span class="text-sm text-text-secondary font-mono">{container}</span>
        <span class="flex items-center gap-1.5">
          {#if status === 'connecting'}
            <span class="w-2 h-2 rounded-full bg-warning animate-pulse"></span>
            <span class="text-xs text-warning">Connecting...</span>
          {:else if status === 'connected'}
            <span class="w-2 h-2 rounded-full bg-success"></span>
            <span class="text-xs text-success">Connected</span>
          {:else if status === 'disconnected'}
            <span class="w-2 h-2 rounded-full bg-tertiary"></span>
            <span class="text-xs text-text-tertiary">Disconnected</span>
          {:else}
            <span class="w-2 h-2 rounded-full bg-error"></span>
            <span class="text-xs text-error">Error</span>
          {/if}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <Select
          bind:value={shell}
          onchange={() => { terminal?.clear(); connect(); }}
          options={[
            { value: '/bin/sh', label: '/bin/sh (default)' },
            { value: '/bin/bash', label: '/bin/bash' },
            { value: '/bin/ash', label: '/bin/ash (Alpine)' },
            { value: '/bin/zsh', label: '/bin/zsh' },
          ]}
          compact
        />
        <button
          onclick={reconnect}
          class="btn btn-sm btn-ghost"
          title="Reconnect"
        >
          <RefreshCw size={16} />
        </button>
        <button
          onclick={handleClose}
          class="btn btn-sm btn-ghost"
          title="Close"
        >
          <X size={16} />
        </button>
      </div>
    </div>

    <!-- Terminal - click to focus -->
    <div
      bind:this={terminalContainer}
      onclick={focusTerminal}
      class="flex-1 min-h-0 cursor-text"
      style="background: #0d1117; padding: 8px;"
    ></div>

    <!-- Status bar -->
    <div class="flex items-center justify-between px-4 py-2 border-t border-border bg-surface-0 text-xs text-text-tertiary shrink-0">
      <span>{namespace}/{pod}/{container}</span>
      {#if status === 'error'}
        <span class="text-warning">Try a different shell if "{shell}" is not available</span>
      {:else}
        <span>Shell: {shell}</span>
      {/if}
    </div>
  </div>
</div>

<style>
  :global(.xterm) {
    height: 100% !important;
  }
  :global(.xterm-viewport) {
    overflow-y: auto !important;
  }
  :global(.xterm-screen) {
    height: 100% !important;
  }
</style>
