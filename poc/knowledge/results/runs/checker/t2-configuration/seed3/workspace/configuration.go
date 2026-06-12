package configuration

import (
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
	var cfg Config

	// Port — default 8080
	if v, ok := source("HELIOS_PORT"); ok {
		port, err := strconv.Atoi(v)
		if err != nil {
			return cfg, fmt.Errorf("HELIOS_PORT: %w", err)
		}
		if port < 1 || port > 65535 {
			return cfg, fmt.Errorf("HELIOS_PORT: value %d out of range [1, 65535]", port)
		}
		cfg.Port = port
	} else {
		cfg.Port = 8080
	}

	// Name — default "helios"
	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return cfg, fmt.Errorf("HELIOS_NAME: must not be empty")
		}
		cfg.Name = v
	} else {
		cfg.Name = "helios"
	}

	// Debug — default false
	if v, ok := source("HELIOS_DEBUG"); ok {
		debug, err := strconv.ParseBool(v)
		if err != nil {
			return cfg, fmt.Errorf("HELIOS_DEBUG: %w", err)
		}
		cfg.Debug = debug
	} else {
		cfg.Debug = false
	}

	return cfg, nil
}