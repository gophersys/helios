// The worktree TREE model — the pure transform from the gateway's flat, slash-separated file list
// into the nested directory tree the file-tree widget renders. One concept, one home: the folding
// rule lives here (not in the component), so the tree shape is unit-testable and the widget stays
// declarative. Pure + cheap — the widget recomputes it on every refresh.
import type { WorktreeFile } from './worktreeFiles.svelte';

/** A node in the rendered worktree tree: either a directory (with ordered children) or a file (a
 *  leaf carrying its full relative path so a click selects it). `name` is the segment shown at this
 *  level; `path` is the full slash-path (the directory's accumulated prefix, or the file's path). */
export type TreeNode = DirectoryNode | FileNode;

/** A directory node — a named folder with its ordered child nodes (directories first, then files,
 *  each alphabetical), so the tree reads like a file browser. */
export interface DirectoryNode {
  kind: 'directory';
  name: string;
  path: string;
  children: TreeNode[];
}

/** A file node — a leaf carrying the full relative path (the selection key) + its size/mtime. */
export interface FileNode {
  kind: 'file';
  name: string;
  path: string;
  size: number;
  modifiedUnix: number;
}

/** buildTree folds a flat worktree file list into a nested tree, with directories sorted before
 *  files and each level ordered alphabetically (a stable, file-browser reading order). A path with
 *  no slash is a root-level file; a path like `init/product/PRODUCT.md` nests under init → product.
 *  Pure: the same input always yields the same tree, so the widget can recompute it on every commit. */
export function buildTree(files: readonly WorktreeFile[]): TreeNode[] {
  const root: DirectoryNode = { kind: 'directory', name: '', path: '', children: [] };
  // An index of directory nodes by their accumulated path, so repeated prefixes reuse one node.
  const directories = new Map<string, DirectoryNode>();
  directories.set('', root);

  for (const file of files) {
    const segments = file.path.split('/').filter((segment) => segment.length > 0);
    if (segments.length === 0) continue;
    const fileName = segments[segments.length - 1];
    const directorySegments = segments.slice(0, -1);

    let parent = root;
    let accumulated = '';
    for (const segment of directorySegments) {
      accumulated = accumulated === '' ? segment : `${accumulated}/${segment}`;
      let directory = directories.get(accumulated);
      if (!directory) {
        directory = { kind: 'directory', name: segment, path: accumulated, children: [] };
        directories.set(accumulated, directory);
        parent.children.push(directory);
      }
      parent = directory;
    }
    parent.children.push({
      kind: 'file',
      name: fileName,
      path: file.path,
      size: file.size,
      modifiedUnix: file.modifiedUnix,
    });
  }

  sortChildren(root);
  return root.children;
}

/** sortChildren orders one directory's children (directories first, then files; each group
 *  alphabetical, case-insensitive) and recurses. Mutates in place — the tree is freshly built each
 *  call, so the mutation never escapes buildTree. */
function sortChildren(directory: DirectoryNode): void {
  directory.children.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'directory' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  });
  for (const child of directory.children) {
    if (child.kind === 'directory') sortChildren(child);
  }
}
