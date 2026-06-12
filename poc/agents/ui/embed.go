// Package ui provides the web UI for monitoring and controlling headless OMP agents.
// It embeds all frontend assets and provides HTTP handlers that plug into the main
// agent runtime server.
package ui

import (
	"embed"
	"fmt"
	"html/template"
	"io/fs"
	"net/http"
	"path"
	"strings"
)

//go:embed static/*
var staticFiles embed.FS

// Handler returns an http.Handler that serves the embedded UI.
// Root path serves index.html; /static/ serves assets.
func Handler() (http.Handler, error) {
	mux := http.NewServeMux()

	staticFS, err := fs.Sub(staticFiles, "static")
	if err != nil {
		return nil, fmt.Errorf("ui: failed to create sub fs: %w", err)
	}

	// Serve static assets with proper cache headers
	fileServer := http.FileServer(http.FS(staticFS))
	mux.Handle("GET /ui/static/", http.StripPrefix("/ui/static/", cacheMiddleware(fileServer)))

	// Serve index.html for all UI routes (SPA)
	indexHandler := serveIndex(staticFS)
	mux.HandleFunc("GET /ui", indexHandler)
	mux.HandleFunc("GET /ui/", indexHandler)
	mux.HandleFunc("GET /ui/agents/{id}", indexHandler)
	mux.HandleFunc("GET /ui/bridge", indexHandler)
	mux.HandleFunc("GET /ui/bridge/{id}", indexHandler)

	return mux, nil
}

func serveIndex(staticFS fs.FS) http.HandlerFunc {
	// Pre-parse the template for speed
	tmpl := template.Must(template.New("index.html").Parse(
		`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Helios Agent Runtime</title>
<link rel="stylesheet" href="/ui/static/styles.css">
</head>
<body>
<div id="app"></div>
<script src="/ui/static/app.js"></script>
</body>
</html>`,
	))

	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		tmpl.Execute(w, nil)
	}
}

func cacheMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ext := path.Ext(r.URL.Path)
		// Cache static assets for 1 year, CSS/JS for 1 hour
		if ext == ".css" || ext == ".js" {
			w.Header().Set("Cache-Control", "public, max-age=3600")
		} else if ext == ".html" {
			w.Header().Set("Cache-Control", "no-cache")
		} else {
			w.Header().Set("Cache-Control", "public, max-age=86400")
		}
		next.ServeHTTP(w, r)
	})
}

// IsUIRequest returns true if the request path targets the UI.
func IsUIRequest(r *http.Request) bool {
	return strings.HasPrefix(r.URL.Path, "/ui") ||
		r.URL.Path == "/" ||
		r.URL.Path == ""
}

// RedirectToUI writes a redirect to /ui
func RedirectToUI(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "/ui", http.StatusFound)
}