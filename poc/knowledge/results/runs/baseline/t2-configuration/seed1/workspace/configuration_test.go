package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func envSource(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestLoadDefaults(t *testing.T) {
	cfg, err := Load(envSource(nil))
	if err != nil {
		t.Fatalf("Load with no env: unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want %q", cfg.Name, "helios")
	}
	if cfg.Debug != false {
		t.Errorf("Debug = %v, want false", cfg.Debug)
	}
}

func TestLoadPort(t *testing.T) {
	tests := []struct {
		name    string
		value   string
		want    int
		wantErr bool
	}{
		{"valid", "4000", 4000, false},
		{"boundary low", "1", 1, false},
		{"boundary high", "65535", 65535, false},
		{"negative", "-1", 0, true},
		{"zero", "0", 0, true},
		{"too high", "65536", 0, true},
		{"not a number", "abc", 0, true},
		{"empty", "", 0, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg, err := Load(envSource(map[string]string{"HELIOS_PORT": tt.value}))
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Port != tt.want {
				t.Errorf("Port = %d, want %d", cfg.Port, tt.want)
			}
		})
	}
}

func TestLoadPortNumError(t *testing.T) {
	_, err := Load(envSource(map[string]string{"HELIOS_PORT": "notanumber"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	var numErr *strconv.NumError
	if !errors.As(err, &numErr) {
		t.Fatalf("expected *strconv.NumError, got %T: %v", err, err)
	}
	if numErr.Func != "Atoi" || numErr.Num != "notanumber" {
		t.Errorf("NumError fields: Func=%q Num=%q", numErr.Func, numErr.Num)
	}
}

func TestLoadPortRangeError(t *testing.T) {
	_, err := Load(envSource(map[string]string{"HELIOS_PORT": "0"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	var numErr *strconv.NumError
	if !errors.As(err, &numErr) {
		t.Fatalf("expected *strconv.NumError, got %T: %v", err, err)
	}
	if !errors.Is(numErr.Err, strconv.ErrRange) {
		t.Errorf("expected ErrRange, got %v", numErr.Err)
	}
}

func TestLoadName(t *testing.T) {
	tests := []struct {
		name    string
		value   string
		want    string
		wantErr bool
	}{
		{"valid", "myapp", "myapp", false},
		{"empty", "", "", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg, err := Load(envSource(map[string]string{"HELIOS_NAME": tt.value}))
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Name != tt.want {
				t.Errorf("Name = %q, want %q", cfg.Name, tt.want)
			}
		})
	}
}

func TestLoadNameErrSyntax(t *testing.T) {
	_, err := Load(envSource(map[string]string{"HELIOS_NAME": ""}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, strconv.ErrSyntax) {
		t.Errorf("expected strconv.ErrSyntax, got %v", err)
	}
}

func TestLoadDebug(t *testing.T) {
	tests := []struct {
		name    string
		value   string
		want    bool
		wantErr bool
	}{
		{"true", "true", true, false},
		{"false", "false", false, false},
		{"1", "1", true, false},
		{"0", "0", false, false},
		{"T", "T", true, false},
		{"F", "F", false, false},
		{"bad", "yesplease", false, true},
		{"empty", "", false, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg, err := Load(envSource(map[string]string{"HELIOS_DEBUG": tt.value}))
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Debug != tt.want {
				t.Errorf("Debug = %v, want %v", cfg.Debug, tt.want)
			}
		})
	}
}

func TestLoadCombined(t *testing.T) {
	cfg, err := Load(envSource(map[string]string{
		"HELIOS_PORT":  "9000",
		"HELIOS_NAME":  "myservice",
		"HELIOS_DEBUG": "true",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 9000 {
		t.Errorf("Port = %d, want 9000", cfg.Port)
	}
	if cfg.Name != "myservice" {
		t.Errorf("Name = %q, want %q", cfg.Name, "myservice")
	}
	if cfg.Debug != true {
		t.Errorf("Debug = %v, want true", cfg.Debug)
	}
}