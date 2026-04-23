/**
 * Lightweight Python syntax highlighter for pytest tracebacks.
 *
 * Renders colored output for:
 * - Keywords (def, class, if, for, import, assert, return, etc.)
 * - Strings (single/double quoted)
 * - Comments (# ...)
 * - Numbers
 * - Decorators (@...)
 * - Built-in functions (print, len, sum, etc.)
 * - Pytest markers (> for current line, E for error lines)
 * - File paths (tests/foo.py:123: ErrorType)
 */

export interface HighlightedLine {
  lineNum: number | null;  // source line number (null for non-code lines)
  segments: { text: string; cls: string }[];
  isError: boolean;        // E prefix line
  isMarker: boolean;       // > prefix line
  isFilePath: boolean;     // file:line: Error line
  filePath?: string;       // extracted file path
  fileLineNum?: number;    // extracted line number
}

// VSCode Dark+ color scheme
const CLR = {
  keyword:   'color: #569cd6',           // blue — def, if, for, import, assert
  control:   'color: #c586c0',           // magenta — return, yield, raise, from, as
  constant:  'color: #569cd6',           // blue — True, False, None
  self:      'color: #569cd6',           // blue — self
  builtin:   'color: #dcdcaa',           // yellow — print, len, sum
  function:  'color: #dcdcaa',           // yellow — function calls
  string:    'color: #ce9178',           // brownish orange — strings
  comment:   'color: #6a9955; font-style: italic',  // green italic — comments
  number:    'color: #b5cea8',           // light green — numbers
  decorator: 'color: #dcdcaa',           // yellow — @decorators
  ident:     'color: #9cdcfe',           // light blue — variables
  operator:  'color: #d4d4d4',           // light gray — operators, punctuation
  type:      'color: #4ec9b0',           // teal — class names, types
  fstring:   'color: #ce9178',           // brownish orange — f-string prefix
};

const PY_KEYWORDS = new Set([
  'def', 'class', 'if', 'elif', 'else', 'for', 'while',
  'with', 'try', 'except', 'finally',
  'pass', 'break', 'continue', 'and', 'or', 'not', 'in', 'is',
  'lambda', 'del', 'global', 'nonlocal', 'assert',
]);

const PY_CONTROL = new Set([
  'return', 'yield', 'raise', 'import', 'from', 'as',
]);

const PY_CONSTANTS = new Set(['None', 'True', 'False']);

const PY_BUILTINS = new Set([
  'print', 'len', 'sum', 'range', 'int', 'str', 'float', 'bool', 'list',
  'dict', 'set', 'tuple', 'type', 'isinstance', 'hasattr', 'getattr',
  'setattr', 'super', 'next', 'iter', 'any', 'all', 'round', 'abs',
  'min', 'max', 'sorted', 'reversed', 'enumerate', 'zip', 'map', 'filter',
  'open', 'repr', 'format', 'id', 'hex', 'oct', 'bin', 'chr', 'ord',
]);

function highlightPythonLine(code: string): { text: string; cls: string }[] {
  const segments: { text: string; cls: string }[] = [];
  let i = 0;

  while (i < code.length) {
    // Comments
    if (code[i] === '#') {
      segments.push({ text: code.slice(i), cls: CLR.comment });
      break;
    }

    // Strings (single and double quoted, including f-strings and triple quotes)
    if (code[i] === '"' || code[i] === "'") {
      const quote = code[i];
      const isTriple = code.slice(i, i + 3) === quote.repeat(3);
      const end = isTriple ? quote.repeat(3) : quote;
      const start = i;
      i += isTriple ? 3 : 1;
      while (i < code.length) {
        if (code[i] === '\\') { i += 2; continue; }
        if (code.slice(i, i + end.length) === end) { i += end.length; break; }
        i++;
      }
      segments.push({ text: code.slice(start, i), cls: CLR.string });
      continue;
    }

    // f/b/r string prefix
    if ((code[i] === 'f' || code[i] === 'b' || code[i] === 'r') &&
        i + 1 < code.length && (code[i + 1] === '"' || code[i + 1] === "'")) {
      segments.push({ text: code[i], cls: CLR.fstring });
      i++;
      continue;
    }

    // Numbers
    if (/\d/.test(code[i]) && (i === 0 || /[\s(=,[\]:{+\-*/]/.test(code[i - 1]))) {
      const start = i;
      while (i < code.length && /[\d.xXa-fA-F_]/.test(code[i])) i++;
      segments.push({ text: code.slice(start, i), cls: CLR.number });
      continue;
    }

    // Words (keywords, builtins, identifiers)
    if (/[a-zA-Z_]/.test(code[i])) {
      const start = i;
      while (i < code.length && /[a-zA-Z0-9_]/.test(code[i])) i++;
      const word = code.slice(start, i);
      // Check if followed by ( — function call
      const nextNonSpace = code.slice(i).trimStart()[0];
      if (word === 'self') {
        segments.push({ text: word, cls: CLR.self });
      } else if (PY_CONSTANTS.has(word)) {
        segments.push({ text: word, cls: CLR.constant });
      } else if (PY_KEYWORDS.has(word)) {
        segments.push({ text: word, cls: CLR.keyword });
      } else if (PY_CONTROL.has(word)) {
        segments.push({ text: word, cls: CLR.control });
      } else if (PY_BUILTINS.has(word)) {
        segments.push({ text: word, cls: CLR.builtin });
      } else if (nextNonSpace === '(') {
        segments.push({ text: word, cls: CLR.function });
      } else if (word[0] === word[0].toUpperCase() && /[a-z]/.test(word.slice(1))) {
        // PascalCase = likely a class/type
        segments.push({ text: word, cls: CLR.type });
      } else {
        segments.push({ text: word, cls: CLR.ident });
      }
      continue;
    }

    // Decorators
    if (code[i] === '@') {
      const start = i;
      i++;
      while (i < code.length && /[a-zA-Z0-9_.]/.test(code[i])) i++;
      segments.push({ text: code.slice(start, i), cls: CLR.decorator });
      continue;
    }

    // Operators and punctuation
    if ('()[]{}:,.=<>+-*/%!&|^~'.includes(code[i])) {
      segments.push({ text: code[i], cls: CLR.operator });
      i++;
      continue;
    }

    // Whitespace and everything else
    segments.push({ text: code[i], cls: '' });
    i++;
  }

  return segments;
}

/**
 * Parse a pytest traceback string into highlighted lines.
 */
export function highlightTraceback(traceback: string): HighlightedLine[] {
  const lines = traceback.split('\n');
  const result: HighlightedLine[] = [];

  // First pass: find the file path line to get the actual line number
  // "tests/foo.py:215: AssertionError" → errorLineNum = 215
  let errorLineNum = 0;
  for (const raw of lines) {
    const m = raw.match(/^(\S+\.py):(\d+):\s*/);
    if (m) { errorLineNum = parseInt(m[2]); break; }
  }

  // Track source line numbers — count code lines backwards from the error line
  // The > marker line IS the error line, code lines before it count down
  let codeLines = 0;
  for (const raw of lines) {
    if (raw.startsWith('>')) break;
    if (raw.startsWith('    ') && !raw.match(/^\w+\s*=\s*</)) codeLines++;
  }
  // The first code line = errorLineNum - codeLines
  let inCodeBlock = false;
  let codeLineNum = errorLineNum > 0 ? errorLineNum - codeLines : 0;

  for (const raw of lines) {
    // File path line: "tests/foo.py:123: AssertionError"
    const fileMatch = raw.match(/^(\S+\.py):(\d+):\s*(.*)$/);
    if (fileMatch) {
      result.push({
        lineNum: null,
        segments: [
          { text: fileMatch[1], cls: 'color: #4fc1ff; text-decoration: underline' },
          { text: ':', cls: 'color: #6a737d' },
          { text: fileMatch[2], cls: 'color: #b5cea8' },
          { text: ': ', cls: 'color: #6a737d' },
          { text: fileMatch[3], cls: 'color: #f14c4c; font-weight: bold' },
        ],
        isError: false,
        isMarker: false,
        isFilePath: true,
        filePath: fileMatch[1],
        fileLineNum: parseInt(fileMatch[2]),
      });
      continue;
    }

    // Error lines: "E       AssertionError: ..."
    if (raw.startsWith('E ') || raw.startsWith('E  ')) {
      result.push({
        lineNum: null,
        segments: [
          { text: 'E', cls: 'color: #f14c4c; font-weight: bold' },
          { text: raw.slice(1), cls: 'color: #f14c4c' },
        ],
        isError: true,
        isMarker: false,
        isFilePath: false,
      });
      continue;
    }

    // Marker line: ">       assert result.passed, ("
    if (raw.startsWith('>')) {
      const code = raw.slice(1);
      const trimmed = code.trimStart();
      const indent = code.length - trimmed.length;
      result.push({
        lineNum: null,
        segments: [
          { text: '>', cls: 'color: #cca700; font-weight: bold' },
          { text: ' '.repeat(indent), cls: '' },
          ...highlightPythonLine(trimmed),
        ],
        isError: false,
        isMarker: true,
        isFilePath: false,
      });
      continue;
    }

    // Variable assignment: "self = <...>"
    if (raw.match(/^\w+\s*=\s*</)) {
      const eqIdx = raw.indexOf('=');
      result.push({
        lineNum: null,
        segments: [
          { text: raw.slice(0, eqIdx), cls: 'color: #9cdcfe' },
          { text: '=', cls: 'color: #d4d4d4' },
          { text: raw.slice(eqIdx + 1), cls: 'color: #6a737d' },
        ],
        isError: false,
        isMarker: false,
        isFilePath: false,
      });
      continue;
    }

    // Code lines (indented with spaces — the test source code)
    if (raw.startsWith('    ')) {
      const trimmed = raw.trimStart();
      const indent = raw.length - trimmed.length;

      // Detect start of function definition for line numbering
      if (trimmed.startsWith('def ') && !inCodeBlock) {
        inCodeBlock = true;
      }

      result.push({
        lineNum: inCodeBlock ? codeLineNum++ : null,
        segments: [
          { text: ' '.repeat(indent), cls: '' },
          ...highlightPythonLine(trimmed),
        ],
        isError: false,
        isMarker: false,
        isFilePath: false,
      });
      continue;
    }

    // Empty lines or anything else
    if (raw.trim() === '') {
      inCodeBlock = false;
      result.push({
        lineNum: null,
        segments: [{ text: ' ', cls: '' }],
        isError: false,
        isMarker: false,
        isFilePath: false,
      });
    } else {
      result.push({
        lineNum: null,
        segments: [{ text: raw, cls: 'color: #8b949e' }],
        isError: false,
        isMarker: false,
        isFilePath: false,
      });
    }
  }

  return result;
}
