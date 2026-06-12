package check

import (
	"go/ast"
	"go/types"
	"strings"

	"golang.org/x/tools/go/packages"
)

// All returns every compiled rule oracle, in rule-ID order.
func All() []Checker {
	return []Checker{
		{Rule: "go/benchmark-loop", Run: benchmarkLoop},
		{Rule: "go/constructor-purity", Run: constructorPurity},
		{Rule: "go/context-first", Run: contextFirst},
		{Rule: "go/environment-confinement", Run: environmentConfinement},
		{Rule: "go/error-wrapping", Run: errorWrapping},
		{Rule: "go/errors-astype", Run: errorsAsType},
		{Rule: "go/interface-size", Run: interfaceSize},
		{Rule: "go/return-concrete", Run: returnConcrete},
		{Rule: "go/slog-multihandler", Run: slogMultiHandler},
		{Rule: "go/waitgroup-go", Run: waitGroupGo},
	}
}

// ---- shared helpers ---------------------------------------------------------

// calleeFunc resolves a call expression to its *types.Func, if any.
func calleeFunc(info *types.Info, call *ast.CallExpr) *types.Func {
	var id *ast.Ident
	switch fun := ast.Unparen(call.Fun).(type) {
	case *ast.Ident:
		id = fun
	case *ast.SelectorExpr:
		id = fun.Sel
	case *ast.IndexExpr: // generic instantiation, e.g. errors.AsType[*T](err)
		switch x := ast.Unparen(fun.X).(type) {
		case *ast.Ident:
			id = x
		case *ast.SelectorExpr:
			id = x.Sel
		}
	}
	if id == nil {
		return nil
	}
	obj := info.Uses[id]
	if obj == nil {
		obj = info.Defs[id]
	}
	fn, _ := obj.(*types.Func)
	return fn
}

// pkgFunc returns (packagePath, funcName) for a resolved callee, or "","".
func pkgFunc(fn *types.Func) (string, string) {
	if fn == nil || fn.Pkg() == nil {
		return "", ""
	}
	return fn.Pkg().Path(), fn.Name()
}

// isStdlibPath reports whether a package path belongs to the standard library
// (first path segment has no dot, unlike module paths).
func isStdlibPath(path string) bool {
	first := path
	if i := strings.Index(path, "/"); i >= 0 {
		first = path[:i]
	}
	return first != "" && !strings.Contains(first, ".")
}

// isContextType reports whether t is context.Context.
func isContextType(t types.Type) bool {
	named, ok := t.(*types.Named)
	if !ok {
		return false
	}
	obj := named.Obj()
	return obj.Pkg() != nil && obj.Pkg().Path() == "context" && obj.Name() == "Context"
}

func isErrorType(t types.Type) bool {
	return types.Identical(t, types.Universe.Lookup("error").Type())
}

// implementsError reports whether t (or *t) implements the error interface.
func implementsError(t types.Type) bool {
	errType := types.Universe.Lookup("error").Type().Underlying().(*types.Interface)
	return types.Implements(t, errType) || types.Implements(types.NewPointer(t), errType)
}

// eachFuncDecl walks all function declarations in non-injected files.
func eachFuncDecl(ctx *Context, fn func(file *ast.File, decl *ast.FuncDecl)) {
	for _, file := range ctx.Pkg.Syntax {
		for _, decl := range file.Decls {
			if fd, ok := decl.(*ast.FuncDecl); ok && fd.Body != nil && !ctx.isVerifyFile(fd.Pos()) {
				fn(file, fd)
			}
		}
	}
}

// ---- go/constructor-purity --------------------------------------------------

func constructorPurity(ctx *Context) []Violation {
	if ctx.Pkg.Name == "main" {
		return nil
	}
	var out []Violation
	var impureReason map[*types.Func]string
	if ctx.Options.TransitivePurity {
		impureReason = packageImpurity(ctx)
	}
	eachFuncDecl(ctx, func(_ *ast.File, fd *ast.FuncDecl) {
		if fd.Recv != nil || ctx.isTestFile(fd.Pos()) {
			return
		}
		name := fd.Name.Name
		if name != "New" && !strings.HasPrefix(name, "New") {
			return
		}
		ast.Inspect(fd.Body, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			fn := calleeFunc(ctx.Pkg.TypesInfo, call)
			path, fname := pkgFunc(fn)
			if impureCall(path, fname) {
				out = append(out, ctx.violation("go/constructor-purity", call.Pos(),
					"constructor %s directly calls %s.%s; constructors must be pure — inject this effect as a dependency", name, path, fname))
			} else if reason, found := impureReason[fn]; found {
				out = append(out, ctx.violation("go/constructor-purity", call.Pos(),
					"constructor %s calls %s, which (transitively) calls %s; constructors must be pure — inject this effect as a dependency", name, fn.Name(), reason))
			}
			return true
		})
	})
	return out
}

// packageImpurity computes a fixpoint over the package-local call graph:
// which functions (transitively) reach a forbidden call. Only CALL edges
// propagate — assigning an adapter value (deps.Clock = systemClock{}) does
// not call its methods, so the defaulting-adapter exception survives v2.
func packageImpurity(ctx *Context) map[*types.Func]string {
	direct := map[*types.Func]string{}   // fn -> "pkg.Name" it calls directly
	edges := map[*types.Func][]*types.Func{} // caller -> package-local callees

	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) || ctx.isTestFile(file.Pos()) {
			continue
		}
		for _, decl := range file.Decls {
			fd, ok := decl.(*ast.FuncDecl)
			if !ok || fd.Body == nil {
				continue
			}
			caller, _ := ctx.Pkg.TypesInfo.Defs[fd.Name].(*types.Func)
			if caller == nil {
				continue
			}
			ast.Inspect(fd.Body, func(n ast.Node) bool {
				call, ok := n.(*ast.CallExpr)
				if !ok {
					return true
				}
				callee := calleeFunc(ctx.Pkg.TypesInfo, call)
				if callee == nil {
					return true
				}
				if path, name := pkgFunc(callee); impureCall(path, name) {
					if _, seen := direct[caller]; !seen {
						direct[caller] = path + "." + name
					}
				} else if callee.Pkg() != nil && callee.Pkg().Path() == ctx.Pkg.PkgPath {
					edges[caller] = append(edges[caller], callee)
				}
				return true
			})
		}
	}

	// fixpoint propagation
	impure := map[*types.Func]string{}
	for fn, reason := range direct {
		impure[fn] = reason
	}
	for changed := true; changed; {
		changed = false
		for caller, callees := range edges {
			if _, already := impure[caller]; already {
				continue
			}
			for _, callee := range callees {
				if reason, found := impure[callee]; found {
					impure[caller] = reason
					changed = true
					break
				}
			}
		}
	}
	return impure
}

func impureCall(path, name string) bool {
	switch path {
	case "time":
		switch name {
		case "Now", "Sleep", "After", "Tick", "NewTicker", "NewTimer", "AfterFunc":
			return true
		}
	case "os":
		switch name {
		case "Getenv", "LookupEnv", "Environ", "Open", "OpenFile", "ReadFile",
			"WriteFile", "Create", "ReadDir", "Remove", "RemoveAll", "Mkdir", "MkdirAll":
			return true
		}
	case "net":
		return strings.HasPrefix(name, "Dial") || strings.HasPrefix(name, "Listen")
	case "net/http":
		switch name {
		case "Get", "Post", "PostForm", "Head":
			return true
		}
	case "math/rand", "math/rand/v2":
		return true
	case "crypto/rand":
		return name == "Read" || name == "Int"
	}
	return false
}

// ---- go/environment-confinement ----------------------------------------------

func environmentConfinement(ctx *Context) []Violation {
	if ctx.Pkg.Name == "main" {
		return nil
	}
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) || ctx.isTestFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			path, fname := pkgFunc(calleeFunc(ctx.Pkg.TypesInfo, call))
			if path == "os" && (fname == "Getenv" || fname == "LookupEnv" || fname == "Environ") {
				out = append(out, ctx.violation("go/environment-confinement", call.Pos(),
					"library package %q reads the process environment (os.%s); only package main may — inject a source instead", ctx.Pkg.Name, fname))
			}
			return true
		})
	}
	return out
}

// ---- go/error-wrapping --------------------------------------------------------

func errorWrapping(ctx *Context) []Violation {
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			path, fname := pkgFunc(calleeFunc(ctx.Pkg.TypesInfo, call))
			if path == "fmt" && fname == "Errorf" && len(call.Args) > 1 {
				lit, ok := ast.Unparen(call.Args[0]).(*ast.BasicLit)
				if !ok {
					return true
				}
				verbs := formatVerbs(lit.Value)
				for i, verb := range verbs {
					argIndex := i + 1
					if argIndex >= len(call.Args) {
						break
					}
					if verb != "v" && verb != "s" {
						continue
					}
					argType := ctx.Pkg.TypesInfo.TypeOf(call.Args[argIndex])
					if argType != nil && isErrorType(argType) {
						out = append(out, ctx.violation("go/error-wrapping", call.Args[argIndex].Pos(),
							"fmt.Errorf formats an error with %%%s, destroying the error tree; wrap with %%w instead", verb))
					}
				}
			}
			// errors.New("..." + err.Error()) and friends
			if path == "errors" && fname == "New" {
				for _, arg := range call.Args {
					if containsErrorErrorCall(ctx.Pkg.TypesInfo, arg) {
						out = append(out, ctx.violation("go/error-wrapping", arg.Pos(),
							"error built by concatenating err.Error(); wrap with fmt.Errorf(\"...: %%w\", err) instead"))
					}
				}
			}
			return true
		})
	}
	return out
}

// formatVerbs extracts the verb letters from a quoted format string literal,
// in argument order. %% is skipped; flags/width/precision are consumed.
func formatVerbs(quoted string) []string {
	var verbs []string
	s := quoted
	for i := 0; i < len(s); i++ {
		if s[i] != '%' {
			continue
		}
		i++
		// consume flags, width, precision, index
		for i < len(s) && strings.ContainsRune("-+# 0123456789.[]*", rune(s[i])) {
			i++
		}
		if i < len(s) {
			if s[i] == '%' {
				continue
			}
			verbs = append(verbs, string(s[i]))
		}
	}
	return verbs
}

func containsErrorErrorCall(info *types.Info, expr ast.Expr) bool {
	found := false
	ast.Inspect(expr, func(n ast.Node) bool {
		call, ok := n.(*ast.CallExpr)
		if !ok {
			return true
		}
		sel, ok := call.Fun.(*ast.SelectorExpr)
		if !ok || sel.Sel.Name != "Error" || len(call.Args) != 0 {
			return true
		}
		if t := info.TypeOf(sel.X); t != nil && isErrorType(t) {
			found = true
			return false
		}
		return true
	})
	return found
}

// ---- go/interface-size ---------------------------------------------------------

const interfaceMethodLimit = 4

func interfaceSize(ctx *Context) []Violation {
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) || ctx.isTestFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			ts, ok := n.(*ast.TypeSpec)
			if !ok || !ts.Name.IsExported() {
				return true
			}
			obj := ctx.Pkg.TypesInfo.Defs[ts.Name]
			if obj == nil {
				return true
			}
			iface, ok := obj.Type().Underlying().(*types.Interface)
			if !ok {
				return true
			}
			if n := iface.NumMethods(); n > interfaceMethodLimit {
				out = append(out, ctx.violation("go/interface-size", ts.Pos(),
					"exported interface %s has %d methods (limit %d); split into composable single-purpose interfaces", ts.Name.Name, n, interfaceMethodLimit))
			}
			return true
		})
	}
	return out
}

// ---- go/return-concrete ---------------------------------------------------------

func returnConcrete(ctx *Context) []Violation {
	if ctx.Pkg.Name == "main" {
		return nil
	}
	var out []Violation
	eachFuncDecl(ctx, func(_ *ast.File, fd *ast.FuncDecl) {
		if !fd.Name.IsExported() || ctx.isTestFile(fd.Pos()) || fd.Type.Results == nil {
			return
		}
		for _, result := range fd.Type.Results.List {
			t := ctx.Pkg.TypesInfo.TypeOf(result.Type)
			if t == nil {
				continue
			}
			named, ok := t.(*types.Named)
			if !ok {
				continue
			}
			if _, isInterface := named.Underlying().(*types.Interface); !isInterface {
				continue
			}
			if isErrorType(t) || isContextType(t) {
				continue
			}
			obj := named.Obj()
			if obj.Pkg() == nil || isStdlibPath(obj.Pkg().Path()) {
				continue // stdlib contracts (io.Reader, slog.Handler, ...) allowed
			}
			out = append(out, ctx.violation("go/return-concrete", result.Type.Pos(),
				"exported %s returns project-defined interface %s; return the concrete type — consumers define their own interfaces", fd.Name.Name, obj.Name()))
		}
	})
	return out
}

// ---- go/context-first ------------------------------------------------------------

func contextFirst(ctx *Context) []Violation {
	var out []Violation
	eachFuncDecl(ctx, func(_ *ast.File, fd *ast.FuncDecl) {
		params := fd.Type.Params
		if params == nil {
			return
		}
		position := 0
		for _, field := range params.List {
			n := len(field.Names)
			if n == 0 {
				n = 1
			}
			t := ctx.Pkg.TypesInfo.TypeOf(field.Type)
			if t != nil && isContextType(t) && position > 0 {
				out = append(out, ctx.violation("go/context-first", field.Pos(),
					"context.Context is parameter %d of %s; it must be the first parameter", position+1, fd.Name.Name))
			}
			position += n
		}
	})
	return out
}

// ---- go/errors-astype --------------------------------------------------------------

func errorsAsType(ctx *Context) []Violation {
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			path, fname := pkgFunc(calleeFunc(ctx.Pkg.TypesInfo, call))
			if path == "errors" && fname == "As" {
				out = append(out, ctx.violation("go/errors-astype", call.Pos(),
					"errors.As(err, &target) is the pre-1.26 form; use t, ok := errors.AsType[T](err)"))
			}
			return true
		})
	}
	return out
}

// ---- go/slog-multihandler -----------------------------------------------------------

func slogMultiHandler(ctx *Context) []Violation {
	slogHandler := lookupInterface(ctx.Pkg, "log/slog", "Handler")
	if slogHandler == nil {
		return nil // package does not use slog
	}
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			ts, ok := n.(*ast.TypeSpec)
			if !ok {
				return true
			}
			obj := ctx.Pkg.TypesInfo.Defs[ts.Name]
			if obj == nil {
				return true
			}
			t := obj.Type()
			if !types.Implements(t, slogHandler) && !types.Implements(types.NewPointer(t), slogHandler) {
				return true
			}
			if holdsMultipleHandlers(t, slogHandler) {
				out = append(out, ctx.violation("go/slog-multihandler", ts.Pos(),
					"type %s is a hand-rolled slog fan-out handler; use slog.NewMultiHandler (Go 1.26) instead", ts.Name.Name))
			}
			return true
		})
	}
	return out
}

// holdsMultipleHandlers reports whether t stores []slog.Handler, is a slice of
// slog.Handler, or has >= 2 slog.Handler fields — the fan-out shape.
func holdsMultipleHandlers(t types.Type, handler *types.Interface) bool {
	handlerType := func(ft types.Type) bool {
		named, ok := ft.(*types.Named)
		if !ok {
			return false
		}
		obj := named.Obj()
		return obj.Pkg() != nil && obj.Pkg().Path() == "log/slog" && obj.Name() == "Handler"
	}
	switch u := t.Underlying().(type) {
	case *types.Slice:
		return handlerType(u.Elem())
	case *types.Struct:
		count := 0
		for i := 0; i < u.NumFields(); i++ {
			ft := u.Field(i).Type()
			if slice, ok := ft.Underlying().(*types.Slice); ok && handlerType(slice.Elem()) {
				return true
			}
			if handlerType(ft) {
				count++
			}
		}
		return count >= 2
	}
	return false
}

// lookupInterface finds a named interface in the package's transitive imports.
func lookupInterface(pkg *packages.Package, path, name string) *types.Interface {
	target := findImport(pkg, path, map[string]bool{})
	if target == nil || target.Types == nil {
		return nil
	}
	obj := target.Types.Scope().Lookup(name)
	if obj == nil {
		return nil
	}
	iface, _ := obj.Type().Underlying().(*types.Interface)
	return iface
}

func findImport(pkg *packages.Package, path string, seen map[string]bool) *packages.Package {
	if pkg.PkgPath == path {
		return pkg
	}
	if seen[pkg.PkgPath] {
		return nil
	}
	seen[pkg.PkgPath] = true
	// Deterministic order.
	keys := make([]string, 0, len(pkg.Imports))
	for k := range pkg.Imports {
		keys = append(keys, k)
	}
	sortStrings(keys)
	for _, k := range keys {
		if found := findImport(pkg.Imports[k], path, seen); found != nil {
			return found
		}
	}
	return nil
}

func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j] < s[j-1]; j-- {
			s[j], s[j-1] = s[j-1], s[j]
		}
	}
}

// ---- go/benchmark-loop ---------------------------------------------------------

func benchmarkLoop(ctx *Context) []Violation {
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) || !ctx.isTestFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			switch stmt := n.(type) {
			case *ast.ForStmt:
				if stmt.Cond == nil {
					return true
				}
				if bin, ok := stmt.Cond.(*ast.BinaryExpr); ok {
					if isBenchmarkN(ctx, bin.Y) || isBenchmarkN(ctx, bin.X) {
						out = append(out, ctx.violation("go/benchmark-loop", stmt.Pos(),
							"benchmark iterates with b.N; use `for b.Loop()` (Go 1.24+) — setup stays unmeasured and dead-code elimination is prevented"))
					}
				}
			case *ast.RangeStmt:
				if isBenchmarkN(ctx, stmt.X) {
					out = append(out, ctx.violation("go/benchmark-loop", stmt.Pos(),
						"benchmark iterates with `range b.N`; use `for b.Loop()` (Go 1.24+)"))
				}
			}
			return true
		})
	}
	return out
}

// isBenchmarkN reports whether expr is the selector b.N on a *testing.B.
func isBenchmarkN(ctx *Context, expr ast.Expr) bool {
	sel, ok := ast.Unparen(expr).(*ast.SelectorExpr)
	if !ok || sel.Sel.Name != "N" {
		return false
	}
	t := ctx.Pkg.TypesInfo.TypeOf(sel.X)
	if t == nil {
		return false
	}
	if ptr, ok := t.(*types.Pointer); ok {
		t = ptr.Elem()
	}
	named, ok := t.(*types.Named)
	if !ok {
		return false
	}
	obj := named.Obj()
	return obj.Pkg() != nil && obj.Pkg().Path() == "testing" && obj.Name() == "B"
}

// ---- go/waitgroup-go -------------------------------------------------------------

// waitGroupGo flags the inline Add/go/Done triple: a `go func(){...}()` whose
// body calls (*sync.WaitGroup).Done. Decoupled lifecycles (Add here, goroutine
// elsewhere) are the documented exception and are not flagged.
func waitGroupGo(ctx *Context) []Violation {
	var out []Violation
	for _, file := range ctx.Pkg.Syntax {
		if ctx.isVerifyFile(file.Pos()) {
			continue
		}
		ast.Inspect(file, func(n ast.Node) bool {
			goStmt, ok := n.(*ast.GoStmt)
			if !ok {
				return true
			}
			lit, ok := goStmt.Call.Fun.(*ast.FuncLit)
			if !ok {
				return true
			}
			ast.Inspect(lit.Body, func(inner ast.Node) bool {
				call, ok := inner.(*ast.CallExpr)
				if !ok {
					return true
				}
				if fn := calleeFunc(ctx.Pkg.TypesInfo, call); fn != nil && fn.Name() == "Done" && isWaitGroupMethod(fn) {
					out = append(out, ctx.violation("go/waitgroup-go", goStmt.Pos(),
						"inline wg.Add/go/Done pattern; use wg.Go(func(){...}) (Go 1.25+) — Done and Add become unforgettable"))
					return false
				}
				return true
			})
			return true
		})
	}
	return out
}

func isWaitGroupMethod(fn *types.Func) bool {
	sig, ok := fn.Type().(*types.Signature)
	if !ok || sig.Recv() == nil {
		return false
	}
	t := sig.Recv().Type()
	if ptr, ok := t.(*types.Pointer); ok {
		t = ptr.Elem()
	}
	named, ok := t.(*types.Named)
	if !ok {
		return false
	}
	obj := named.Obj()
	return obj.Pkg() != nil && obj.Pkg().Path() == "sync" && obj.Name() == "WaitGroup"
}
