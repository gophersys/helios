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
	cfg := Config{
		Port:  8080,
		Name:  "helios",
		Debug: false,
	}

	if v, ok := source("HELIOS_PORT"); ok {
		n, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("helios port: %w", err)
		}
		if n < 1 || n > 65535 {
			return Config{}, fmt.Errorf("helios port: value %d out of range 1–65535", n)
		}
		cfg.Port = n
	}

	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return Config{}, fmt.Errorf("helios name: must not be empty")
		}
		cfg.Name = v
	}

	if v, ok := source("HELIOS_DEBUG"); ok {
		b, err := strconv.ParseBool(v)
		if err != nil {
			return Config{}, fmt.Errorf("helios debug: %w", err)
		}
		cfg.Debug = b
	}

	return cfg, nil
}