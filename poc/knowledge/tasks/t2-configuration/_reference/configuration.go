// Package configuration is the reference implementation used to validate the
// held-out verify suite. It is never shown to the agent.
package configuration

import (
	"errors"
	"fmt"
	"strconv"
)

type Source func(key string) (value string, found bool)

type Config struct {
	Port  int
	Name  string
	Debug bool
}

func Load(source Source) (Config, error) {
	configuration := Config{Port: 8080, Name: "helios"}
	if raw, found := source("HELIOS_PORT"); found {
		port, err := strconv.Atoi(raw)
		if err != nil {
			return Config{}, fmt.Errorf("configuration: parse HELIOS_PORT: %w", err)
		}
		if port < 1 || port > 65535 {
			return Config{}, fmt.Errorf("configuration: HELIOS_PORT %d out of range 1-65535", port)
		}
		configuration.Port = port
	}
	if raw, found := source("HELIOS_NAME"); found {
		if raw == "" {
			return Config{}, errors.New("configuration: HELIOS_NAME must not be empty")
		}
		configuration.Name = raw
	}
	if raw, found := source("HELIOS_DEBUG"); found {
		debug, err := strconv.ParseBool(raw)
		if err != nil {
			return Config{}, fmt.Errorf("configuration: parse HELIOS_DEBUG: %w", err)
		}
		configuration.Debug = debug
	}
	return configuration, nil
}
