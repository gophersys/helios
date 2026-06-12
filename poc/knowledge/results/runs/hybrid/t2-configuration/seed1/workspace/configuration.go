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

	if v, ok := source("HELIOS_PORT"); ok {
		p, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("HELIOS_PORT: %w", err)
		}
		if p < 1 || p > 65535 {
			return Config{}, fmt.Errorf("HELIOS_PORT: value %d out of range [1, 65535]", p)
		}
		cfg.Port = p
	}

	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return Config{}, errors.New("HELIOS_NAME: value must not be empty")
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
