package gitrepository

import (
	"context"
	"strings"
)

// status parses `git status --porcelain=v2 --branch -z` into a Status. v2 porcelain is the
// stable, machine-readable surface: branch headers, then one record per changed path, NUL-
// terminated so a path with spaces/newlines parses unambiguously.
func (g *systemGit) status(ctx context.Context, op *InspectOp) (InspectResult, error) {
	out, err := g.run(ctx, op.Worktree, nil, nil, "status", "--porcelain=v2", "--branch", "-z")
	if err != nil {
		return InspectResult{}, err
	}
	status := parseStatusV2(splitNUL(out))
	return InspectResult{Status: status}, nil
}

// parseStatusV2 turns the NUL-split records of `status --porcelain=v2 --branch -z` into a
// Status. The record grammar (git-status(1) "Porcelain Format Version 2"):
//
//	# branch.head <name>        — the checked-out branch ("(detached)" for detached HEAD)
//	# branch.oid <sha>          — the HEAD commit ("(initial)" for an unborn branch)
//	# branch.upstream <ref>     — the upstream ref (present only when configured)
//	# branch.ab +<a> -<b>       — ahead/behind
//	1 <XY> ...                  — an ordinary changed entry
//	2 <XY> ... <NUL> <origPath> — a renamed/copied entry (orig path is the next NUL field)
//	u <XY> ...                  — an unmerged (conflicted) entry
//	? <path>                    — an untracked path
func parseStatusV2(records []string) Status {
	status := Status{Clean: true}
	for i := 0; i < len(records); i++ {
		record := records[i]
		switch {
		case strings.HasPrefix(record, "# branch.head "):
			name := strings.TrimPrefix(record, "# branch.head ")
			if name != "(detached)" {
				if parsed, perr := ParseBranchName(name); perr == nil {
					status.Branch = parsed
				}
			}
		case strings.HasPrefix(record, "# branch.oid "):
			oid := strings.TrimPrefix(record, "# branch.oid ")
			if oid != "(initial)" {
				status.Head = commitIDFromHex(oid)
			}
		case strings.HasPrefix(record, "# branch.upstream "):
			up := strings.TrimPrefix(record, "# branch.upstream ")
			status.Upstream = parseUpstreamRef(up)
		case strings.HasPrefix(record, "# branch.ab "):
			ahead, behind := parseAheadBehind(strings.TrimPrefix(record, "# branch.ab "))
			status.Ahead, status.Behind = ahead, behind
		case strings.HasPrefix(record, "1 "):
			status.Changes = append(status.Changes, parseOrdinaryEntry(record))
			status.Clean = false
		case strings.HasPrefix(record, "2 "):
			change := parseRenamedEntry(record)
			// A type-2 record is followed by its original path in the NEXT NUL field.
			if i+1 < len(records) {
				change.OldPath = records[i+1]
				i++
			}
			status.Changes = append(status.Changes, change)
			status.Clean = false
		case strings.HasPrefix(record, "u "):
			status.Changes = append(status.Changes, FileChange{
				Path:   fieldAfter(record, statusV2PathFieldUnmerged),
				Status: ChangeConflicted,
			})
			status.Clean = false
		case strings.HasPrefix(record, "? "):
			status.Changes = append(status.Changes, FileChange{
				Path:   strings.TrimPrefix(record, "? "),
				Status: ChangeUntracked,
			})
			status.Clean = false
		}
	}
	return status
}

// field indices into a v2 porcelain ordinary/renamed entry (space-separated head, then the
// path). The path is the last space-separated field for type 1; for type 2 the path is the
// field after the rename score.
const (
	statusV2PathFieldUnmerged = 10 // `u` records: 10 head fields then the path
)

// parseOrdinaryEntry parses a "1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>" record.
func parseOrdinaryEntry(record string) FileChange {
	fields := strings.SplitN(record, " ", 9)
	change := FileChange{}
	if len(fields) >= 9 {
		change.Path = fields[8]
		xy := fields[1]
		change.Status, change.Staged = changeFromXY(xy)
	}
	return change
}

// parseRenamedEntry parses a "2 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <Xscore> <path>" record.
func parseRenamedEntry(record string) FileChange {
	fields := strings.SplitN(record, " ", 10)
	change := FileChange{Status: ChangeRenamed}
	if len(fields) >= 10 {
		change.Path = fields[9]
		_, change.Staged = changeFromXY(fields[1])
		change.Status = ChangeRenamed
	}
	return change
}

// changeFromXY maps the two-letter XY staging/worktree status of a v2 entry to a ChangeKind
// and whether the change is staged (the index half, X, is non-".").
func changeFromXY(xy string) (kind ChangeKind, staged bool) {
	if len(xy) < 2 {
		return ChangeModified, false
	}
	x, y := xy[0], xy[1]
	staged = x != '.'
	primary := x
	if primary == '.' {
		primary = y
	}
	switch primary {
	case 'A':
		return ChangeAdded, staged
	case 'D':
		return ChangeDeleted, staged
	case 'R':
		return ChangeRenamed, staged
	case 'C':
		return ChangeRenamed, staged
	case 'U':
		return ChangeConflicted, staged
	default:
		return ChangeModified, staged
	}
}

// fieldAfter returns the nth space-separated field of record (the path field of an unmerged
// entry), or "" if absent.
func fieldAfter(record string, n int) string {
	fields := strings.Split(record, " ")
	if n < len(fields) {
		return strings.Join(fields[n:], " ")
	}
	return ""
}

// parseUpstreamRef turns "origin/main" into a Ref{Remote:"origin", Branch:"main"}.
func parseUpstreamRef(s string) Ref {
	remote, branch, ok := strings.Cut(s, "/")
	if !ok {
		return Ref{}
	}
	parsed, err := ParseBranchName(branch)
	if err != nil {
		return Ref{Remote: remote}
	}
	return Ref{Remote: remote, Branch: parsed}
}

// parseAheadBehind parses "+3 -2" into (3, 2).
func parseAheadBehind(s string) (ahead, behind int) {
	for _, token := range strings.Fields(s) {
		switch {
		case strings.HasPrefix(token, "+"):
			ahead = atoiSafe(strings.TrimPrefix(token, "+"))
		case strings.HasPrefix(token, "-"):
			behind = atoiSafe(strings.TrimPrefix(token, "-"))
		}
	}
	return ahead, behind
}

// branches parses `git for-each-ref` over refs/heads (and refs/remotes when IncludeRemote)
// into []Branch with tip + upstream + ahead/behind.
func (g *systemGit) branches(ctx context.Context, op *InspectOp) (InspectResult, error) {
	format := strings.Join([]string{
		"%(refname)", "%(objectname)", "%(upstream)",
		"%(upstream:track,nobracket)",
	}, "%00")
	args := []string{"for-each-ref", "--format=" + format, "refs/heads"}
	if op.IncludeRemote {
		args = append(args, "refs/remotes")
	}
	out, err := g.run(ctx, op.Root, nil, nil, args...)
	if err != nil {
		return InspectResult{}, err
	}

	var branches []Branch
	for _, line := range scanLines(out) {
		fields := strings.Split(line, "\x00")
		if len(fields) < 4 {
			continue
		}
		refname := fields[0]
		isRemote := strings.HasPrefix(refname, "refs/remotes/")
		name := shortBranch(refname)
		if isRemote && strings.HasSuffix(name, "/HEAD") {
			continue // skip the symbolic remote HEAD pointer
		}
		parsed, perr := ParseBranchName(name)
		if perr != nil {
			continue
		}
		ahead, behind := parseTrack(fields[3])
		branches = append(branches, Branch{
			Name:     parsed,
			Tip:      commitIDFromHex(fields[1]),
			IsRemote: isRemote,
			Upstream: parseUpstreamFullRef(fields[2]),
			Ahead:    ahead,
			Behind:   behind,
		})
	}
	return InspectResult{Branches: branches}, nil
}

// parseUpstreamFullRef turns "refs/remotes/origin/main" into a Ref.
func parseUpstreamFullRef(s string) Ref {
	if s == "" {
		return Ref{}
	}
	short := strings.TrimPrefix(s, "refs/remotes/")
	return parseUpstreamRef(short)
}

// parseTrack parses for-each-ref's "ahead N, behind M" track field (nobracket form).
func parseTrack(s string) (ahead, behind int) {
	for _, segment := range strings.Split(s, ",") {
		segment = strings.TrimSpace(segment)
		switch {
		case strings.HasPrefix(segment, "ahead "):
			ahead = atoiSafe(strings.TrimPrefix(segment, "ahead "))
		case strings.HasPrefix(segment, "behind "):
			behind = atoiSafe(strings.TrimPrefix(segment, "behind "))
		}
	}
	return ahead, behind
}

// worktrees parses `git worktree list --porcelain` into []WorktreeInfo. The first listed
// worktree is the main working tree (IsMain).
func (g *systemGit) worktrees(ctx context.Context, op *InspectOp) (InspectResult, error) {
	out, err := g.run(ctx, op.Root, nil, nil, "worktree", "list", "--porcelain")
	if err != nil {
		return InspectResult{}, err
	}

	var infos []WorktreeInfo
	var current WorktreeInfo
	var have bool
	first := true
	flush := func() {
		if have {
			infos = append(infos, current)
		}
	}
	for _, line := range scanLines(out) {
		switch {
		case strings.HasPrefix(line, "worktree "):
			flush()
			current = WorktreeInfo{Path: strings.TrimPrefix(line, "worktree "), IsMain: first}
			first = false
			have = true
		case strings.HasPrefix(line, "HEAD "):
			current.Tip = commitIDFromHex(strings.TrimPrefix(line, "HEAD "))
		case strings.HasPrefix(line, "branch "):
			current.Branch = func() BranchName {
				name := shortBranch(strings.TrimPrefix(line, "branch "))
				parsed, perr := ParseBranchName(name)
				if perr != nil {
					return BranchName{}
				}
				return parsed
			}()
		case line == "":
			flush()
			have = false
		}
	}
	flush()
	return InspectResult{Worktrees: infos}, nil
}
