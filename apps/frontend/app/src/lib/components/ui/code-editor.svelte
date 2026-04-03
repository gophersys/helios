<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view';
  import { EditorState, type Extension, Compartment } from '@codemirror/state';
  import { defaultKeymap, indentWithTab } from '@codemirror/commands';
  import { HighlightStyle, syntaxHighlighting, bracketMatching, StreamLanguage } from '@codemirror/language';
  import { tags } from '@lezer/highlight';
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

  // Capture initial prop values for the theme (CodeMirror theme is set once at mount)
  const initialHeight = height;
  const initialMaxHeight = maxHeight;

  // ── VS Code Dark+ inspired theme ──────────────────────
  const vscodeDarkTheme = EditorView.theme({
    '&': {
      backgroundColor: '#1e1e2e',
      color: '#cdd6f4',
      fontSize: '13px',
      ...(initialHeight ? { height: initialHeight } : {}),
      ...(initialMaxHeight && !initialHeight ? { maxHeight: initialMaxHeight } : {}),
      overflow: 'auto',
    },
    '.cm-content': {
      fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      caretColor: '#cdd6f4',
      padding: '8px 0',
    },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: '#cdd6f4' },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
      backgroundColor: '#44475a',
    },
    '.cm-panels': { backgroundColor: '#181825', color: '#cdd6f4' },
    '.cm-panels.cm-panels-top': { borderBottom: '1px solid #313244' },
    '.cm-panels.cm-panels-bottom': { borderTop: '1px solid #313244' },
    '.cm-searchMatch': { backgroundColor: '#585b7066', outline: '1px solid #585b70' },
    '.cm-searchMatch.cm-searchMatch-selected': { backgroundColor: '#89b4fa33' },
    '.cm-activeLine': { backgroundColor: '#1e1e2e80' },
    '.cm-selectionMatch': { backgroundColor: '#585b7044' },
    '&.cm-focused .cm-matchingBracket': { backgroundColor: '#585b7066', outline: '1px solid #89b4fa55' },
    '.cm-gutters': {
      backgroundColor: '#181825',
      color: '#585b70',
      border: 'none',
      minWidth: '48px',
    },
    '.cm-activeLineGutter': { backgroundColor: '#1e1e2e', color: '#a6adc8' },
    '.cm-foldPlaceholder': { backgroundColor: '#313244', border: 'none', color: '#a6adc8' },
    '.cm-tooltip': { backgroundColor: '#1e1e2e', border: '1px solid #313244', color: '#cdd6f4' },
    '.cm-tooltip .cm-tooltip-arrow:before': { borderTopColor: '#313244', borderBottomColor: '#313244' },
    '.cm-tooltip .cm-tooltip-arrow:after': { borderTopColor: '#1e1e2e', borderBottomColor: '#1e1e2e' },
    '.cm-tooltip-autocomplete': { '& > ul > li[aria-selected]': { backgroundColor: '#313244', color: '#cdd6f4' } },
    '.cm-scroller': { overflow: 'auto' },
    '.cm-lint-marker': { width: '0.6em' },
    // Search panel
    '.cm-panel.cm-search': { backgroundColor: '#181825' },
    '.cm-panel.cm-search input': {
      backgroundColor: '#313244', color: '#cdd6f4', border: '1px solid #45475a',
      borderRadius: '4px', padding: '2px 6px',
    },
    '.cm-panel.cm-search button': {
      backgroundColor: '#313244', color: '#cdd6f4', border: '1px solid #45475a',
      borderRadius: '4px', padding: '2px 8px',
    },
  }, { dark: true });

  // VS Code Dark+ syntax highlighting (blues, purples, greens)
  const vscodeDarkHighlight = HighlightStyle.define([
    { tag: tags.keyword, color: '#cba6f7' },           // purple — if, then, else, fi, for, do, done
    { tag: tags.controlKeyword, color: '#cba6f7' },     // purple — control flow
    { tag: tags.definitionKeyword, color: '#cba6f7' },  // purple — function
    { tag: tags.operatorKeyword, color: '#cba6f7' },    // purple — operators
    { tag: tags.modifier, color: '#cba6f7' },           // purple
    { tag: tags.comment, color: '#6c7086', fontStyle: 'italic' }, // grey-green comments
    { tag: tags.lineComment, color: '#6c7086', fontStyle: 'italic' },
    { tag: tags.blockComment, color: '#6c7086', fontStyle: 'italic' },
    { tag: tags.string, color: '#a6e3a1' },             // green — "strings"
    { tag: tags.special(tags.string), color: '#a6e3a1' },
    { tag: tags.number, color: '#fab387' },             // peach — numbers
    { tag: tags.integer, color: '#fab387' },
    { tag: tags.float, color: '#fab387' },
    { tag: tags.variableName, color: '#89b4fa' },       // blue — $VAR
    { tag: tags.definition(tags.variableName), color: '#89b4fa' },
    { tag: tags.function(tags.variableName), color: '#89dceb' }, // teal — function names
    { tag: tags.propertyName, color: '#89b4fa' },       // blue
    { tag: tags.attributeName, color: '#89b4fa' },      // blue
    { tag: tags.atom, color: '#fab387' },               // peach — true, false
    { tag: tags.bool, color: '#fab387' },
    { tag: tags.null, color: '#fab387' },
    { tag: tags.operator, color: '#89dceb' },           // teal — |, &&, ||
    { tag: tags.punctuation, color: '#bac2de' },        // subtext — (), {}, ;
    { tag: tags.paren, color: '#f9e2af' },              // yellow — parentheses
    { tag: tags.bracket, color: '#f9e2af' },            // yellow — brackets
    { tag: tags.meta, color: '#f38ba8' },               // red — shebang, special
    { tag: tags.name, color: '#cdd6f4' },               // default text
    { tag: tags.content, color: '#cdd6f4' },
    { tag: tags.labelName, color: '#89dceb' },          // teal
    { tag: tags.inserted, color: '#a6e3a1' },           // green
    { tag: tags.deleted, color: '#f38ba8' },            // red
    { tag: tags.changed, color: '#f9e2af' },            // yellow
    { tag: tags.invalid, color: '#f38ba8' },            // red
  ]);

  onMount(() => {
    const extensions: Extension[] = [
      lineNumbers(),
      bracketMatching(),
      vscodeDarkTheme,
      syntaxHighlighting(vscodeDarkHighlight),
      StreamLanguage.define(shell),
      search(),
      keymap.of(searchKeymap),
      lintGutter(),
      diagnosticsCompartment.of([]),
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

  $effect(() => {
    if (view && value !== view.state.doc.toString()) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: value },
      });
    }
  });

  $effect(() => {
    if (view && diagnostics) {
      view.dispatch(setDiagnostics(view.state, diagnostics));
    }
  });
</script>

<div bind:this={container} class="overflow-hidden {className}"></div>
