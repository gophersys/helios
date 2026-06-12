package ui

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHandler_ReturnsIndexHTML(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui")
	if err != nil {
		t.Fatalf("GET /ui: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", res.StatusCode)
	}

	body, _ := io.ReadAll(res.Body)
	html := string(body)
	if !strings.Contains(html, "<!DOCTYPE html>") {
		t.Error("response is not HTML")
	}
	if !strings.Contains(html, "Helios Agent Runtime") {
		t.Error("missing title")
	}
	if !strings.Contains(html, "app.js") {
		t.Error("missing app.js script reference")
	}
	if !strings.Contains(html, "styles.css") {
		t.Error("missing styles.css link")
	}
}

func TestHandler_IndexHTMLAtRoot(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/")
	if err != nil {
		t.Fatalf("GET /ui/: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", res.StatusCode)
	}
	body, _ := io.ReadAll(res.Body)
	if !strings.Contains(string(body), "Helios Agent Runtime") {
		t.Error("trailing slash doesn't return index")
	}
}

func TestHandler_ServesCSS(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/static/styles.css")
	if err != nil {
		t.Fatalf("GET styles.css: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", res.StatusCode)
	}
	body, _ := io.ReadAll(res.Body)
	if !strings.Contains(string(body), "--bg-primary") {
		t.Error("CSS missing theme variables")
	}
	if !strings.Contains(string(body), "--font-mono") {
		t.Error("CSS missing mono font definition")
	}
	ct := res.Header.Get("Content-Type")
	if !strings.Contains(ct, "css") && !strings.Contains(ct, "text/plain") {
		t.Logf("Content-Type: %s", ct)
	}
}

func TestHandler_ServesJS(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/static/app.js")
	if err != nil {
		t.Fatalf("GET app.js: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", res.StatusCode)
	}
	body, _ := io.ReadAll(res.Body)
	js := string(body)
	if !strings.Contains(js, "App") || !strings.Contains(js, "function init") {
		t.Error("JS missing core App definition or init function")
	}
	if !strings.Contains(js, "handleCreateAgent") {
		t.Error("JS missing agent creation handler")
	}
	if !strings.Contains(js, "connectMetricsSSE") {
		t.Error("JS missing SSE metrics connection")
	}
	if !strings.Contains(js, "connectEventsSSE") {
		t.Error("JS missing SSE events connection")
	}
	if !strings.Contains(js, "renderBridgeView") {
		t.Error("JS missing bridge view rendering")
	}
	if !strings.Contains(js, "renderAgentDetail") {
		t.Error("JS missing agent detail rendering")
	}
	ct := res.Header.Get("Content-Type")
	if !strings.Contains(ct, "javascript") && !strings.Contains(ct, "text/plain") {
		t.Logf("Content-Type: %s", ct)
	}
}

func TestHandler_NotFoundReturnsIndex(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/some/invalid/path")
	if err != nil {
		t.Fatalf("GET unknown: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200 (SPA fallback), got %d", res.StatusCode)
	}
	body, _ := io.ReadAll(res.Body)
	if !strings.Contains(string(body), "Helios Agent Runtime") {
		t.Error("unknown path doesn't return index")
	}
}

func TestHandler_AgentRouteReturnsIndex(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/agents/test-agent-id")
	if err != nil {
		t.Fatalf("GET /ui/agents/test-agent-id: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", res.StatusCode)
	}
	body, _ := io.ReadAll(res.Body)
	if !strings.Contains(string(body), "Helios Agent Runtime") {
		t.Error("agent route doesn't return index")
	}
}

func TestHandler_BridgeRouteReturnsIndex(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/bridge")
	if err != nil {
		t.Fatalf("GET /ui/bridge: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", res.StatusCode)
	}
	body, _ := io.ReadAll(res.Body)
	if !strings.Contains(string(body), "Helios Agent Runtime") {
		t.Error("bridge route doesn't return index")
	}
}
func TestIsUIRequest_True(t *testing.T) {
	for _, p := range []string{"/ui", "/ui/", "/ui/agents/abc", "/ui/bridge", "/ui/static/app.js", "/"} {
		req := httptest.NewRequest("GET", p, nil)
		if !IsUIRequest(req) {
			t.Errorf("IsUIRequest false for %q", p)
		}
	}
}

func TestIsUIRequest_False(t *testing.T) {
	for _, p := range []string{"/api/v1/agents", "/api/v1/health", "/favicon.ico"} {
		req := httptest.NewRequest("GET", p, nil)
		if IsUIRequest(req) {
			t.Errorf("IsUIRequest true for %q", p)
		}
	}
}

func TestCacheMiddleware_SetsHeaders(t *testing.T) {
	handler := cacheMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	tests := []struct {
		path  string
		wants string // substring of Cache-Control
	}{
		{"/ui/static/styles.css", "max-age=3600"},
		{"/ui/static/app.js", "max-age=3600"},
		{"/ui/index.html", "no-cache"},
		{"/ui/static/logo.png", "max-age=86400"},
	}

	for _, tt := range tests {
		req := httptest.NewRequest("GET", tt.path, nil)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		cc := w.Header().Get("Cache-Control")
		if !strings.Contains(cc, tt.wants) {
			t.Errorf("%s: Cache-Control %q missing %q", tt.path, cc, tt.wants)
		}
	}
}

func TestContentIntegrity_HTMLNoBOM(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui")
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()

	body, _ := io.ReadAll(res.Body)
	if len(body) > 0 && body[0] == 0xEF {
		t.Error("HTML starts with BOM")
	}
	if len(body) > 0 && body[0] == 0xFE {
		t.Error("HTML starts with UTF-16 BOM")
	}
}

func TestAppJS_ExportsExpectedFunctions(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/static/app.js")
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()

	body, _ := io.ReadAll(res.Body)
	js := string(body)

	// Core runtime functions
	required := []string{
		"App =",
		"function init",
		"function render",
		"function renderSidebar",
		"function renderEmptyState",
		"function selectAgent",
		"function renderAgentDetail",
		"function renderBridgeView",
		"function renderMetricsGrid",
		"function renderEventLog",
		"function appendAgentEvent",
		"function appendAgentMetric",
		"function renderChatMessage",
		"function renderToolCall",
		"function handleCreateAgent",
		"function handlePrompt",
		"function handleStartAgent",
		"function handleAbortAgent",
		"function handleShutdownAgent",
		"function handleBridgeWorkerPrompt",
		"function showToast",
		"function refreshBridgeLog",
		"function switchAgentTab",
		"function updateConnectionStatus",
		"function navigate",
		"function escapeHtml",
	}

	for _, fn := range required {
		if !strings.Contains(js, fn) {
			t.Errorf("JS missing: %s", fn)
		}
	}
}

func TestCSS_RequiredClasses(t *testing.T) {
	handler, _ := Handler()
	server := httptest.NewServer(handler)
	defer server.Close()

	res, err := http.Get(server.URL + "/ui/static/styles.css")
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()

	body, _ := io.ReadAll(res.Body)
	css := string(body)

	required := []string{
		".sidebar",
		".main-content",
		".agent-card",
		".agent-card-header",
		".message",
		".message.user",
		".message.assistant",
		".tool-call",
		".thinking-block",
		".bridge-layout",
		".bridge-column",
		".bridge-center",
		".bridge-arrow",
		".bridge-log-entry",
		".metrics-panel",
		".metric-card",
		".event-log",
		".event",
		".status-badge",
		".tabs",
		".tab",
		".task-form",
		".modal-overlay",
		".modal",
		".toast-container",
		".spinner",
	}

	for _, cls := range required {
		if !strings.Contains(css, cls) {
			t.Errorf("CSS missing class: %s", cls)
		}
	}
}