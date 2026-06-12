// Package configuration resolves structured configuration from a key-value source.
package configuration

import (
	"fmt"
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

// Config holds the parsed application configuration.
type Config struct {
	Port  int
	Name  string
	Debug bool
}

// Load reads configuration keys through source and returns a validated Config.
// A key that is present but fails to parse is returned as an error that
// preserves the underlying parse error (e.g. *strconv.NumError for a bad
// port). A present-but-empty HELIOS_NAME is an error.
func Load(source Source) (Config, error) {
	cfg := Config{
		Port:  8080,
		Name:  "helios",
		Debug: false,
	}

	if v, ok := source("HELIOS_PORT"); ok {
		n, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_PORT: %w", err)
		}
		if n < 1 || n > 65535 {
			return Config{}, fmt.Errorf("HELIOS_PORT: value %d out of range [1, 65535]", n)
		}
		cfg.Port = n
	}

	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return Config{}, fmt.Errorf("HELIOS_NAME: value must not be empty")
		}
		cfg.Name = v
	}

	if v, ok := source("HELIOS_DEBUG"); ok {
		b, err := strconv.ParseBool(v)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_DEBUG: %w", err)
		}
		cfg.Debug = b
	}

	return cfg, nil
}