package configuration

import (
	"errors"
	"fmt"
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

type Config struct {
	Port  int
	Name  string
	Debug bool
}

func Load(source Source) (Config, error) {
	cfg := Config{
		Port:  8080,
		Name:  "helios",
		Debug: false,
	}

	// HELIOS_PORT
	if val, ok := source("HELIOS_PORT"); ok {
		port, err := strconv.Atoi(val)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_PORT: %w", err)
		}
		if port < 1 || port > 65535 {
			return Config{}, fmt.Errorf("HELIOS_PORT: must be 1–65535, got %d", port)
		}
		cfg.Port = port
	}

	// HELIOS_NAME
	if val, ok := source("HELIOS_NAME"); ok {
		if val == "" {
			return Config{}, errors.New("HELIOS_NAME: must not be empty")
		}
		cfg.Name = val
	}

	// HELIOS_DEBUG
	if val, ok := source("HELIOS_DEBUG"); ok {
		debug, err := strconv.ParseBool(val)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_DEBUG: %w", err)
		}
		cfg.Debug = debug
	}

	return cfg, nil
}
