package gitrepository

import (
	"context"
	"strings"
)

// diff runs `git diff` in the requested mode and parses the result into a bounded Diff.
// NameOnly returns the cheap path+status list; otherwise a unified patch capped at MaxBytes
// (Truncated set at the cap) with binary files flagged, never inlined.
func (g *systemGit) diff(ctx context.Context, op *InspectOp) (InspectResult, error) {
	if op.NameOnly {
		return g.diffNameOnly(ctx, op)
	}
	return g.diffPatch(ctx, op)
}

// diffArgs builds the mode-specific positional args shared by the name-only and patch paths.
func diffArgs(op *InspectOp) (dir string, args []string) {
	switch op.DiffMode {
	case DiffStagedVsHead:
		return op.Worktree, []string{"diff", "--cached"}
	case DiffCommits:
		// From..To over the repository (a gate comparing a branch to base). The two revisions
		// are passed as separate positionals (NOT a "from..to" token) so neither can smuggle a
		// range operator past the argv guard.
		return op.Root, []string{"diff", op.From, op.To}
	default: // DiffWorkingVsHead
		return op.Worktree, []string{"diff", "HEAD"}
	}
}

// diffNameOnly runs `git diff --name-status -z` and returns Path+Status only.
func (g *systemGit) diffNameOnly(ctx context.Context, op *InspectOp) (InspectResult, error) {
	dir, args := diffArgs(op)
	args = append(args, "--name-status", "-z", "--find-renames")
	args = appendPathspec(args, op.Paths)

	out, err := g.run(ctx, dir, nil, nil, args...)
	if err != nil {
		return InspectResult{}, err
	}
	return InspectResult{Diff: Diff{Files: parseNameStatus(splitNUL(out))}}, nil
}

// parseNameStatus parses the NUL-split `--name-status -z` stream. A rename record is
// "R<score>\x00<old>\x00<new>"; an ordinary record is "<X>\x00<path>".
func parseNameStatus(records []string) []FileDiff {
	var files []FileDiff
	for i := 0; i < len(records); i++ {
		code := records[i]
		if code == "" {
			continue
		}
		switch code[0] {
		case 'R', 'C':
			if i+2 < len(records) {
				files = append(files, FileDiff{
					Status:  ChangeRenamed,
					OldPath: records[i+1],
					Path:    records[i+2],
				})
				i += 2
			}
		default:
			if i+1 < len(records) {
				files = append(files, FileDiff{
					Status: statusFromLetter(code[0]),
					Path:   records[i+1],
				})
				i++
			}
		}
	}
	return files
}

// statusFromLetter maps a name-status letter to a ChangeKind.
func statusFromLetter(b byte) ChangeKind {
	switch b {
	case 'A':
		return ChangeAdded
	case 'D':
		return ChangeDeleted
	case 'R':
		return ChangeRenamed
	case 'C':
		return ChangeRenamed
	case 'U':
		return ChangeConflicted
	default:
		return ChangeModified
	}
}

// diffPatch runs `git diff` for a unified patch and parses it into FileDiffs with bounded
// hunks. The patch is requested with a byte budget (MaxBytes) honored by truncating at the
// cap and setting Truncated.
func (g *systemGit) diffPatch(ctx context.Context, op *InspectOp) (InspectResult, error) {
	dir, args := diffArgs(op)
	args = append(args, "--find-renames", "--no-color")
	args = appendPathspec(args, op.Paths)

	out, err := g.run(ctx, dir, nil, nil, args...)
	if err != nil {
		return InspectResult{}, err
	}

	truncated := false
	if int64(len(out)) > op.MaxBytes {
		out = out[:op.MaxBytes]
		truncated = true
	}
	files := parseUnifiedDiff(string(out))
	return InspectResult{Diff: Diff{Files: files, Truncated: truncated}}, nil
}

// appendPathspec appends a "--" pathspec separator and the scoping paths, if any.
func appendPathspec(args, paths []string) []string {
	if len(paths) == 0 {
		return args
	}
	args = append(args, "--")
	return append(args, paths...)
}

// parseUnifiedDiff parses a `git diff` unified patch into per-file FileDiffs with hunks. It
// is a tolerant line scanner over git's stable diff grammar:
//
//	diff --git a/<old> b/<new>
//	[similarity / rename from|to / new file / deleted file …]
//	Binary files a/<x> and b/<y> differ      — a binary file (no hunks)
//	--- a/<old>
//	+++ b/<new>
//	@@ -<oS>,<oL> +<nS>,<nL> @@ …             — a hunk header
//	 <context> / +<added> / -<removed>       — hunk body
func parseUnifiedDiff(patch string) []FileDiff {
	p := &diffParser{}
	for _, line := range strings.Split(patch, "\n") {
		p.consume(line)
	}
	p.flushFile()
	return p.files
}

// diffParser is the line-at-a-time state machine parseUnifiedDiff drives. Splitting the
// per-line dispatch onto methods keeps each unit under the complexity ceiling.
type diffParser struct {
	files   []FileDiff
	current *FileDiff
	hunk    *Hunk
}

// consume routes one patch line to the right state transition.
func (p *diffParser) consume(line string) {
	if strings.HasPrefix(line, "diff --git ") {
		p.beginFile(line)
		return
	}
	if p.current == nil {
		return
	}
	if p.consumeHeader(line) {
		return
	}
	if strings.HasPrefix(line, "@@ ") {
		p.flushHunk()
		h := parseHunkHeader(line)
		p.hunk = &h
		return
	}
	if isPatchMetadata(line) {
		return
	}
	if p.hunk != nil {
		p.consumeBody(line)
	}
}

// beginFile flushes the prior file and starts a new one from a "diff --git" header.
func (p *diffParser) beginFile(line string) {
	p.flushFile()
	old, newPath := parseDiffGitHeader(line)
	p.current = &FileDiff{Path: newPath, Status: ChangeModified}
	if old != newPath && old != "" {
		p.current.OldPath = old
		p.current.Status = ChangeRenamed
	}
}

// consumeHeader handles the per-file extended-header lines, reporting whether it matched.
func (p *diffParser) consumeHeader(line string) bool {
	switch {
	case strings.HasPrefix(line, "new file"):
		p.current.Status = ChangeAdded
	case strings.HasPrefix(line, "deleted file"):
		p.current.Status = ChangeDeleted
	case strings.HasPrefix(line, "rename to "):
		p.current.Path = strings.TrimPrefix(line, "rename to ")
		p.current.Status = ChangeRenamed
	case strings.HasPrefix(line, "rename from "):
		p.current.OldPath = strings.TrimPrefix(line, "rename from ")
		p.current.Status = ChangeRenamed
	case strings.HasPrefix(line, "Binary files "):
		p.current.IsBinary = true
	default:
		return false
	}
	return true
}

// consumeBody appends a hunk-body line and counts added/removed lines.
func (p *diffParser) consumeBody(line string) {
	p.hunk.Text += line + "\n"
	switch {
	case strings.HasPrefix(line, "+"):
		p.current.AddedLines++
	case strings.HasPrefix(line, "-"):
		p.current.RemovedLines++
	}
}

// flushHunk commits the in-progress hunk to the current file.
func (p *diffParser) flushHunk() {
	if p.current != nil && p.hunk != nil {
		p.current.Hunks = append(p.current.Hunks, *p.hunk)
		p.hunk = nil
	}
}

// flushFile commits the in-progress file to the result.
func (p *diffParser) flushFile() {
	p.flushHunk()
	if p.current != nil {
		p.files = append(p.files, *p.current)
		p.current = nil
	}
}

// isPatchMetadata reports the non-body header lines a hunk parser skips.
func isPatchMetadata(line string) bool {
	return strings.HasPrefix(line, "--- ") || strings.HasPrefix(line, "+++ ") || strings.HasPrefix(line, "index ")
}

// parseDiffGitHeader extracts the old and new paths from a "diff --git a/<old> b/<new>" line.
func parseDiffGitHeader(line string) (old, newPath string) {
	rest := strings.TrimPrefix(line, "diff --git ")
	aIndex := strings.Index(rest, "a/")
	bIndex := strings.Index(rest, " b/")
	if aIndex != 0 || bIndex < 0 {
		return "", strings.TrimSpace(rest)
	}
	old = rest[len("a/"):bIndex]
	newPath = rest[bIndex+len(" b/"):]
	return old, newPath
}

// parseHunkHeader parses "@@ -oS,oL +nS,nL @@ <section>" into a Hunk (without body text).
func parseHunkHeader(line string) Hunk {
	hunk := Hunk{Text: line + "\n", OldLines: 1, NewLines: 1}
	body := line
	if idx := strings.Index(line[2:], " @@"); idx >= 0 {
		body = line[2 : idx+2]
	}
	for _, token := range strings.Fields(body) {
		switch {
		case strings.HasPrefix(token, "-"):
			hunk.OldStart, hunk.OldLines = parseRange(strings.TrimPrefix(token, "-"))
		case strings.HasPrefix(token, "+"):
			hunk.NewStart, hunk.NewLines = parseRange(strings.TrimPrefix(token, "+"))
		}
	}
	return hunk
}

// parseRange parses "start,len" (len defaults to 1 when absent).
func parseRange(s string) (start, length int) {
	startStr, lenStr, ok := strings.Cut(s, ",")
	startN := atoiSafe(startStr)
	if !ok {
		return startN, 1
	}
	return startN, atoiSafe(lenStr)
}
