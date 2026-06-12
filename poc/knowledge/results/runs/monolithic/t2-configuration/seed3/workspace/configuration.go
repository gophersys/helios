package configuration

import (
	"errors"
	"fmt"
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

// Config holds the application configuration values.
type Config struct {
	Port  int
	Name  string
	Debug bool
}

// Load reads configuration keys through source and returns a Config.
// Missing keys get defaults. Present-but-invalid values return an error
// whose chain preserves the underlying parse error.
func Load(source Source) (Config, error) {
	var cfg Config
	var errs []error

	// HELIOS_PORT
	if v, ok := source("HELIOS_PORT"); ok {
		port, err := strconv.Atoi(v)
		if err != nil {
			errs = append(errs, fmt.Errorf("HELIOS_PORT: %w", err))
		} else if port < 1 || port > 65535 {
			errs = append(errs, fmt.Errorf("HELIOS_PORT: value %d out of range [1,65535]", port))
		} else {
			cfg.Port = port
		}
	} else {
		cfg.Port = 8080
	}

	// HELIOS_NAME
	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			errs = append(errs, errors.New("HELIOS_NAME: must not be empty"))
		} else {
			cfg.Name = v
		}
	} else {
		cfg.Name = "helios"
	}

	// HELIOS_DEBUG
	if v, ok := source("HELIOS_DEBUG"); ok {
		debug, err := strconv.ParseBool(v)
		if err != nil {
			errs = append(errs, fmt.Errorf("HELIOS_DEBUG: %w", err))
		} else {
			cfg.Debug = debug
		}
	} else {
		cfg.Debug = false
	}

	return cfg, errors.Join(errs...)
}