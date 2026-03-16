<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view';
  import { EditorState } from '@codemirror/state';
  import { defaultKeymap, indentWithTab } from '@codemirror/commands';
  import { syntaxHighlighting, defaultHighlightStyle, bracketMatching, StreamLanguage } from '@codemirror/language';
  import { oneDark } from '@codemirror/theme-one-dark';

  interface Props {
    value: string;
    readonly?: boolean;
    maxHeight?: string;
    onchange?: (value: string) => void;
  }

  let { value, readonly = false, maxHeight = '500px', onchange }: Props = $props();

  let container: HTMLDivElement;
  let view: EditorView | undefined;

  // Simple shell/bash highlighting via StreamLanguage
  const shellLanguage = StreamLanguage.define({
    token(stream) {
      // Comments
      if (stream.match('#')) {
        stream.skipToEnd();
        return 'comment';
      }
      // Strings
      if (stream.match(/"([^"\\]|\\.)*"/)) return 'string';
      if (stream.match(/'([^'\\]|\\.)*'/)) return 'string';
      // Variables
      if (stream.match(/\$\{[^}]+\}/)) return 'variableName.special';
      if (stream.match(/\$[A-Za-z_][A-Za-z0-9_]*/)) return 'variableName.special';
      // Keywords
      if (stream.match(/\b(if|then|else|elif|fi|for|do|done|while|until|case|esac|function|return|local|export|source|set|unset|shift|break|continue|exit|trap|eval|exec|declare|readonly|typeset)\b/)) return 'keyword';
      // Builtins
      if (stream.match(/\b(echo|printf|cd|pwd|ls|cp|mv|rm|mkdir|chmod|chown|cat|grep|sed|awk|find|test|true|false|read|wait|sleep|kill|basename|dirname)\b/)) return 'atom';
      // Numbers
      if (stream.match(/\b\d+\b/)) return 'number';
      // Operators
      if (stream.match(/[|&;><(){}\[\]]/)) return 'operator';
      // Skip
      stream.next();
      return null;
    },
    startState() { return {}; },
  });

  onMount(() => {
    const extensions = [
      lineNumbers(),
      syntaxHighlighting(defaultHighlightStyle),
      bracketMatching(),
      oneDark,
      shellLanguage,
      EditorView.theme({
        '&': { fontSize: '13px', maxHeight, overflow: 'auto' },
        '.cm-scroller': { overflow: 'auto' },
        '.cm-content': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' },
        '.cm-gutters': { borderRight: '1px solid #333', minWidth: '40px' },
      }),
    ];

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
</script>

<div bind:this={container} class="rounded border border-border overflow-hidden"></div>
