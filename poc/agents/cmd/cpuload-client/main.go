package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"text/tabwriter"
	"time"
)

var baseURL string

func main() {
	addr := flag.String("addr", "http://127.0.0.1:8080", "server address")
	dur := flag.Duration("duration", 5*time.Second, "load duration (e.g. 5s, 30s, 1m)")
	workers := flag.Int("workers", 1, "number of CPU workers")
	intensity := flag.Float64("intensity", 1.0, "work intensity multiplier (1.0 = baseline)")
	cancel := flag.String("cancel", "", "cancel a load by ID")
	loadID := flag.String("load", "", "show status of a specific load")
	flag.Parse()

	baseURL = *addr

	switch {
	case *cancel != "":
		doCancel(*cancel)
	case *loadID != "":
		showLoad(*loadID)
	case flag.NArg() == 0 && *loadID == "" && *cancel == "":
		// Default action: start a load
		startLoad(*dur, *workers, *intensity)
	default:
		// extra args = subcommands
		args := flag.Args()
		if len(args) == 0 {
			listLoads()
			return
		}
		switch args[0] {
		case "start":
			startLoad(*dur, *workers, *intensity)
		case "list":
			listLoads()
		case "get":
			if len(args) < 2 {
				fmt.Fprintln(os.Stderr, "usage: cpuload-client get <load_id>")
				os.Exit(1)
			}
			showLoad(args[1])
		case "cancel":
			if len(args) < 2 {
				fmt.Fprintln(os.Stderr, "usage: cpuload-client cancel <load_id>")
				os.Exit(1)
			}
			doCancel(args[1])
		default:
			fmt.Fprintf(os.Stderr, "unknown command: %s (start|list|get|cancel)\n", args[0])
			os.Exit(1)
		}
	}
}

func startLoad(dur time.Duration, workers int, intensity float64) {
	body := map[string]interface{}{
		"duration_ms": dur.Milliseconds(),
		"workers":     workers,
		"intensity":   intensity,
	}
	var resp struct {
		LoadID     string  `json:"load_id"`
		Status     string  `json:"status"`
		DurationMs int64   `json:"duration_ms"`
		Workers    int     `json:"workers"`
		Intensity  float64 `json:"intensity"`
	}
	doJSON("POST", "/load", body, &resp)

	fmt.Printf("Started load %s:\n", resp.LoadID)
	fmt.Printf("  Status:     %s\n", resp.Status)
	fmt.Printf("  Duration:   %d ms\n", resp.DurationMs)
	fmt.Printf("  Workers:    %d\n", resp.Workers)
	fmt.Printf("  Intensity:  %.1f\n", resp.Intensity)
}

func listLoads() {
	var resp struct {
		Loads []struct {
			ID         string  `json:"id"`
			Status     string  `json:"status"`
			DurationMs int64   `json:"duration_ms"`
			Workers    int     `json:"workers"`
			Progress   float64 `json:"progress"`
			Iterations int64   `json:"iterations"`
			StartedAt  string  `json:"started_at"`
		} `json:"loads"`
	}
	doJSON("GET", "/loads", nil, &resp)

	if len(resp.Loads) == 0 {
		fmt.Println("No active or completed loads.")
		return
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tStatus\tWorkers\tProgress\tIterations\tStarted")
	fmt.Fprintln(w, "--\t------\t-------\t--------\t----------\t-------")
	for _, l := range resp.Loads {
		fmt.Fprintf(w, "%s\t%s\t%d\t%.0f%%\t%d\t%s\n",
			l.ID, l.Status, l.Workers, l.Progress*100, l.Iterations, l.StartedAt)
	}
	w.Flush()
}

func showLoad(id string) {
	var resp struct {
		ID         string  `json:"id"`
		Status     string  `json:"status"`
		DurationMs int64   `json:"duration_ms"`
		Workers    int     `json:"workers"`
		Progress   float64 `json:"progress"`
		Iterations int64   `json:"iterations"`
		StartedAt  string  `json:"started_at"`
	}
	doJSON("GET", "/loads/"+id, nil, &resp)

	fmt.Printf("Load %s:\n", resp.ID)
	fmt.Printf("  Status:     %s\n", resp.Status)
	fmt.Printf("  Duration:   %d ms\n", resp.DurationMs)
	fmt.Printf("  Workers:    %d\n", resp.Workers)
	fmt.Printf("  Progress:   %.0f%%\n", resp.Progress*100)
	fmt.Printf("  Iterations: %d\n", resp.Iterations)
	fmt.Printf("  Started at: %s\n", resp.StartedAt)
}

func doCancel(id string) {
	var resp struct {
		Status  string `json:"status"`
		LoadID  string `json:"load_id"`
		Error   string `json:"error"`
	}
	doJSON("POST", "/load/cancel", map[string]string{"load_id": id}, &resp)
	if resp.Error != "" {
		fmt.Fprintf(os.Stderr, "Error: %s\n", resp.Error)
		os.Exit(1)
	}
	fmt.Printf("Cancelled load %s (%s)\n", resp.LoadID, resp.Status)
}

// ── HTTP helpers ──────────────────────────────

var httpClient = &http.Client{Timeout: 30 * time.Second}

func doJSON(method, path string, body, into interface{}) {
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			fmt.Fprintf(os.Stderr, "marshal error: %v\n", err)
			os.Exit(1)
		}
		reqBody = bytes.NewReader(b)
	}

	req, err := http.NewRequest(method, baseURL+path, reqBody)
	if err != nil {
		fmt.Fprintf(os.Stderr, "request error: %v\n", err)
		os.Exit(1)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "http error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		fmt.Fprintf(os.Stderr, "HTTP %d: %s\n", resp.StatusCode, string(bytes.TrimSpace(respBody)))
		os.Exit(1)
	}

	if into != nil {
		if err := json.NewDecoder(resp.Body).Decode(into); err != nil {
			fmt.Fprintf(os.Stderr, "decode error: %v\n", err)
			os.Exit(1)
		}
	}
}