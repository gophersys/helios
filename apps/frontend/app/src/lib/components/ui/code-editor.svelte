<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view';
  import { EditorState, type Extension, Compartment } from '@codemirror/state';
  import { defaultKeymap, indentWithTab } from '@codemirror/commands';
  import { syntaxHighlighting, defaultHighlightStyle, bracketMatching, StreamLanguage } from '@codemirror/language';
  import { oneDark } from '@codemirror/theme-one-dark';
  import { shell } from '@codemirror/legacy-modes/mode/shell';
  import { autocompletion, type CompletionSource } from '@codemirror/autocomplete';
  import { search, searchKeymap } from '@codemirror/search';
  import { setDiagnostics, lintGutter, type Diagnostic } from '@codemirror/lint';

  interface Props {
    value: string;
    readonly?: boolean;
    maxHeight?: string;
    height?: string;
    class?: string;
    completions?: CompletionSource;
    diagnostics?: Diagnostic[];
    onchange?: (value: string) => void;
    oncursorchange?: (line: number, col: number) => void;
  }

  let {
    value,
    readonly = false,
    maxHeight = '500px',
    height,
    class: className = '',
    completions,
    diagnostics,
    onchange,
    oncursorchange,
  }: Props = $props();

  let container: HTMLDivElement;
  let view: EditorView | undefined;
  const diagnosticsCompartment = new Compartment();

  onMount(() => {
    const extensions: Extension[] = [
      lineNumbers(),
      syntaxHighlighting(defaultHighlightStyle),
      bracketMatching(),
      oneDark,
      StreamLanguage.define(shell),
      search(),
      keymap.of(searchKeymap),
      lintGutter(),
      diagnosticsCompartment.of([]),
      EditorView.theme({
        '&': {
          fontSize: '13px',
          ...(height ? { height } : {}),
          ...(maxHeight && !height ? { maxHeight } : {}),
          overflow: 'auto',
        },
        '.cm-scroller': { overflow: 'auto' },
        '.cm-content': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' },
        '.cm-gutters': { borderRight: '1px solid #333', minWidth: '40px' },
      }),
    ];

    if (completions) {
      extensions.push(autocompletion({ override: [completions] }));
    }

    if (readonly) {
      extensions.push(EditorState.readOnly.of(true), EditorView.editable.of(false));
    } else {
      extensions.push(
        keymap.of([...defaultKeymap, indentWithTab]),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            onchange?.(update.state.doc.toString());
          }
          if (update.selectionSet || update.docChanged) {
            const pos = update.state.selection.main.head;
            const line = update.state.doc.lineAt(pos);
            oncursorchange?.(line.number, pos - line.from + 1);
          }
        }),
      );
    }

    view = new EditorView({
      state: EditorState.create({ doc: value, extensions }),
      parent: container,
    });
  });

  onDestroy(() => {
    view?.destroy();
  });

  // Update content when value prop changes externally
  $effect(() => {
    if (view && value !== view.state.doc.toString()) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: value },
      });
    }
  });

  // Update diagnostics when prop changes
  $effect(() => {
    if (view && diagnostics) {
      view.dispatch(setDiagnostics(view.state, diagnostics));
    }
  });
</script>

<div bind:this={container} class="rounded border border-border overflow-hidden {className}"></div>
