<script lang="ts">
  import { Check, AlertTriangle, X, RefreshCw } from 'lucide-svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import Card from '$lib/components/ui/card.svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Diagnostic } from '@codemirror/lint';
  import type { CompletionContext, CompletionResult } from '@codemirror/autocomplete';

  interface Props {
    content: string;
    productId: string;
    readonly?: boolean;
  }

  let { content = $bindable(), productId, readonly = false }: Props = $props();

  let validating = $state(false);
  let validationResult = $state<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null);
  let showValidation = $state(false);
  let cursorLine = $state(1);
  let cursorCol = $state(1);
  let diagnostics = $state<Diagnostic[]>([]);

  // ── Concord SDK autocomplete ────────────────────────────────
  const concordCompletions = [
    { label: '$CONCORD_PRODUCT', type: 'variable', detail: 'Product name' },
    { label: '$CONCORD_BOARD', type: 'variable', detail: 'Board name' },
    { label: '$CONCORD_FW_TYPE', type: 'variable', detail: 'Firmware type (app/mfg)' },
    { label: '$CONCORD_VARIANT', type: 'variable', detail: 'Build variant' },
    { label: '$CONCORD_VERSION', type: 'variable', detail: 'Version string' },
    { label: '$CONCORD_REPO_DIR', type: 'variable', detail: 'Firmware repo directory' },
    { label: '$CONCORD_OUT_DIR', type: 'variable', detail: 'Output artifact directory' },
    { label: '$CONCORD_KEYS_DIR', type: 'variable', detail: 'Signing keys directory' },
    { label: '$CONCORD_CFW_FLAGS', type: 'variable', detail: 'CFW track flags bitmask' },
    { label: '$CONCORD_APP_IDS', type: 'variable', detail: 'JSON map of processor app IDs' },
    { label: 'concord_init', type: 'function', detail: 'Initialize build environment' },
    { label: 'concord_collect_hex', type: 'function', detail: 'Collect hex artifacts' },
    { label: 'concord_collect_cfw', type: 'function', detail: 'Generate and collect CFW files' },
    { label: 'concord_finalize', type: 'function', detail: 'Write build manifest and finalize' },
  ];

  function concordAutocomplete(context: CompletionContext): CompletionResult | null {
    // Match $ prefix for variables
    const varMatch = context.matchBefore(/\$[A-Z_]*/);
    if (varMatch) {
      return {
        from: varMatch.from,
        options: concordCompletions.filter((c) => c.type === 'variable'),
        validFor: /^\$[A-Z_]*$/,
      };
    }

    // Match word for functions
    const wordMatch = context.matchBefore(/concord_?\w*/);
    if (wordMatch && wordMatch.text.length >= 2) {
      return {
        from: wordMatch.from,
        options: concordCompletions.filter((c) => c.type === 'function'),
        validFor: /^concord_?\w*$/,
      };
    }

    return null;
  }

  // ── Validation ──────────────────────────────────────────────
  async function handleValidate(): Promise<void> {
    validating = true;
    validationResult = null;
    try {
      const res = await api.post<ApiResponse<{ valid: boolean; errors: string[]; warnings: string[] }>>(
        `/v2/products/${productId}/recipe/validate`,
        { content }
      );
      validationResult = res.data;
      showValidation = true;

      // Convert validation errors to CodeMirror diagnostics
      const newDiagnostics: Diagnostic[] = [];
      if (res.data.errors) {
        for (const err of res.data.errors) {
          const lineMatch = err.match(/line (\d+)/i);
          const lineNum = lineMatch ? parseInt(lineMatch[1], 10) : 1;
          const lines = content.split('\n');
          const from = lines.slice(0, lineNum - 1).reduce((sum, l) => sum + l.length + 1, 0);
          const to = from + (lines[lineNum - 1]?.length || 0);
          newDiagnostics.push({
            from: Math.min(from, content.length),
            to: Math.min(to, content.length),
            severity: 'error',
            message: err,
            source: 'recipe-validator',
          });
        }
      }
      if (res.data.warnings) {
        for (const warn of res.data.warnings) {
          const lineMatch = warn.match(/line (\d+)/i);
          const lineNum = lineMatch ? parseInt(lineMatch[1], 10) : 1;
          const lines = content.split('\n');
          const from = lines.slice(0, lineNum - 1).reduce((sum, l) => sum + l.length + 1, 0);
          const to = from + (lines[lineNum - 1]?.length || 0);
          newDiagnostics.push({
            from: Math.min(from, content.length),
            to: Math.min(to, content.length),
            severity: 'warning',
            message: warn,
            source: 'recipe-validator',
          });
        }
      }
      diagnostics = newDiagnostics;
    } catch (err: unknown) {
      validationResult = {
        valid: false,
        errors: [err instanceof Error ? err.message : 'Validation request failed'],
        warnings: [],
      };
      showValidation = true;
    } finally {
      validating = false;
    }
  }

  let charCount = $derived(content.length);
  let lineCount = $derived(content.split('\n').length);
</script>

<div class="flex flex-col h-full">
  <!-- Editor fills available space -->
  <div class="flex flex-1 min-h-0">
    <!-- Editor pane -->
    <div class="flex-1 min-w-0 flex flex-col">
      <CodeEditor
        value={content}
        onchange={(v) => (content = v)}
        oncursorchange={(line, col) => {
          cursorLine = line;
          cursorCol = col;
        }}
        completions={concordAutocomplete}
        {diagnostics}
        {readonly}
        height="100%"
        maxHeight=""
        class="flex-1 min-h-0 [&_.cm-editor]:h-full!"
      />
    </div>

    <!-- Validation panel (split view) -->
    {#if showValidation && validationResult}
      <div class="w-80 shrink-0 border-l border-border bg-surface-0 flex flex-col overflow-hidden">
        <Card size="sm" closable onclose={() => (showValidation = false)} class="rounded-none! border-0! border-b! border-border! shrink-0">
          <span class="text-xs font-semibold text-text-primary">Validation</span>
        </Card>
        <div class="flex-1 overflow-y-auto p-3 space-y-2">
          <!-- Status -->
          <div class="flex items-center gap-2 rounded-lg px-3 py-2 {validationResult.valid ? 'bg-success-muted' : 'bg-error-muted'}">
            {#if validationResult.valid}
              <Check size={16} class="text-success shrink-0" />
              <span class="text-xs font-medium text-success">Recipe is valid</span>
            {:else}
              <AlertTriangle size={16} class="text-error shrink-0" />
              <span class="text-xs font-medium text-error">Validation failed</span>
            {/if}
          </div>

          <!-- Errors -->
          {#each validationResult.errors as err}
            <Card size="sm" class="bg-error/5! border-error/20!">
              <div class="flex items-start gap-2">
                <X size={12} class="text-error shrink-0 mt-0.5" />
                <p class="text-2xs text-error wrap-break-word">{err}</p>
              </div>
            </Card>
          {/each}

          <!-- Warnings -->
          {#each validationResult.warnings as warn}
            <Card size="sm" class="bg-warning/5! border-warning/20!">
              <div class="flex items-start gap-2">
                <AlertTriangle size={12} class="text-warning shrink-0 mt-0.5" />
                <p class="text-2xs text-warning wrap-break-word">{warn}</p>
              </div>
            </Card>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <!-- Bottom toolbar -->
  <div class="flex items-center justify-between border-t border-border bg-surface-0 px-4 py-1.5 shrink-0">
    <div class="flex items-center gap-4 text-2xs text-text-tertiary font-mono">
      <span>Ln {cursorLine}, Col {cursorCol}</span>
      <span>{lineCount} lines</span>
      <span>{charCount.toLocaleString()} chars</span>
    </div>
    <div class="flex items-center gap-2">
      <button
        onclick={() => {
          if (showValidation) {
            showValidation = false;
          } else {
            handleValidate();
          }
        }}
        disabled={validating || !content}
        class="btn btn-sm btn-ghost
               {validationResult?.valid === true
                 ? 'text-success! hover:bg-success-muted!'
                 : validationResult?.valid === false
                   ? 'text-error! hover:bg-error-muted!'
                   : ''}"
      >
        {#if validating}
          <RefreshCw size={12} class="animate-spin" />
        {:else if validationResult?.valid === true}
          <Check size={12} />
        {:else if validationResult?.valid === false}
          <AlertTriangle size={12} />
        {:else}
          <Check size={12} />
        {/if}
        Validate
      </button>
    </div>
  </div>
</div>
