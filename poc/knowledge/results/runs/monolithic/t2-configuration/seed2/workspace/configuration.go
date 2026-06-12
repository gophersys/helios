package configuration

import (
	"fmt"
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

// Config holds the application configuration loaded through Source.
type Config struct {
	Port  int
	Name  string
	Debug bool
}

// Load reads configuration keys through source and returns a Config.
// Keys that are present but fail to parse produce an error that preserves
// the underlying parse error for inspection via the errors package.
func Load(source Source) (Config, error) {
	var cfg Config

	// HELIOS_PORT — default 8080
	cfg.Port = 8080
	if val, ok := source("HELIOS_PORT"); ok {
		p, err := strconv.Atoi(val)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_PORT: %w", err)
		}
		if p < 1 || p > 65535 {
			return Config{}, fmt.Errorf("HELIOS_PORT: value %d out of range [1, 65535]", p)
		}
		cfg.Port = p
	}

	// HELIOS_NAME — default "helios", must be non-empty when present
	cfg.Name = "helios"
	if val, ok := source("HELIOS_NAME"); ok {
		if val == "" {
			return Config{}, fmt.Errorf("HELIOS_NAME: must not be empty")
		}
		cfg.Name = val
	}

	// HELIOS_DEBUG — default false
	if val, ok := source("HELIOS_DEBUG"); ok {
		d, err := strconv.ParseBool(val)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_DEBUG: %w", err)
		}
		cfg.Debug = d
	}

	return cfg, nil
}