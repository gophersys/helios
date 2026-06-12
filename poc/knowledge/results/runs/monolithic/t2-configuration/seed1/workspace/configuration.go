package configuration

import (
	"fmt"
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

// Config holds the application configuration.
type Config struct {
	Port  int
	Name  string
	Debug bool
}

// Load reads configuration from source.
func Load(source Source) (Config, error) {
	cfg := Config{
		Port:  8080,
		Name:  "helios",
		Debug: false,
	}

	if v, ok := source("HELIOS_PORT"); ok {
		port, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("configuration: %w", err)
		}
		if port < 1 || port > 65535 {
			return Config{}, fmt.Errorf("configuration: port %d out of range (1-65535)", port)
		}
		cfg.Port = port
	}

	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return Config{}, fmt.Errorf("configuration: HELIOS_NAME must not be empty")
		}
		cfg.Name = v
	}

	if v, ok := source("HELIOS_DEBUG"); ok {
		debug, err := strconv.ParseBool(v)
		if err != nil {
			return Config{}, fmt.Errorf("configuration: %w", err)
		}
		cfg.Debug = debug
	}

	return cfg, nil
}