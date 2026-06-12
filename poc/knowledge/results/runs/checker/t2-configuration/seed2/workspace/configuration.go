// Package configuration resolves configuration keys from a Source into a
// typed Config struct.
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

// Load reads configuration keys through source and returns a parsed Config.
// A key that is present but fails to parse is an error. Present-but-empty
// HELIOS_NAME is an error. Keys not present use defaults documented below.
//
// Keys and defaults:
//
//	HELIOS_PORT  Port  int     "8080"
//	HELIOS_NAME  Name  string  "helios"
//	HELIOS_DEBUG Debug bool    "false"
func Load(source Source) (Config, error) {
	var cfg Config

	// HELIOS_PORT
	portRaw := "8080"
	if v, ok := source("HELIOS_PORT"); ok {
		portRaw = v
	}
	port, err := strconv.Atoi(portRaw)
	if err != nil {
		return cfg, fmt.Errorf("HELIOS_PORT: %w", err)
	}
	if port < 1 || port > 65535 {
		return cfg, fmt.Errorf("HELIOS_PORT: value %d out of range [1, 65535]", port)
	}
	cfg.Port = port

	// HELIOS_NAME
	nameRaw := "helios"
	if v, ok := source("HELIOS_NAME"); ok {
		nameRaw = v
	}
	if nameRaw == "" {
		return cfg, fmt.Errorf("HELIOS_NAME: value must not be empty")
	}
	cfg.Name = nameRaw

	// HELIOS_DEBUG
	debugRaw := "false"
	if v, ok := source("HELIOS_DEBUG"); ok {
		debugRaw = v
	}
	debug, err := strconv.ParseBool(debugRaw)
	if err != nil {
		return cfg, fmt.Errorf("HELIOS_DEBUG: %w", err)
	}
	cfg.Debug = debug

	return cfg, nil
}