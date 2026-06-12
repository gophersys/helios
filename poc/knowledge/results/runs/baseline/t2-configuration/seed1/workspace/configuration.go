package configuration

import (
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

type Config struct {
	Port  int
	Name  string
	Debug bool
}

// Load reads configuration keys from source and returns a Config.
// Keys that are present but fail to parse produce an error that wraps
// the underlying parse error.
func Load(source Source) (Config, error) {
	var cfg Config

	// Port — default 8080
	if v, ok := source("HELIOS_PORT"); ok {
		port, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, err
		}
		if port < 1 || port > 65535 {
			return Config{}, &strconv.NumError{
				Func: "Atoi",
				Num:  v,
				Err:  strconv.ErrRange,
			}
		}
		cfg.Port = port
	} else {
		cfg.Port = 8080
	}

	// Name — default "helios", must be non-empty when present
	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return Config{}, strconv.ErrSyntax
		}
		cfg.Name = v
	} else {
		cfg.Name = "helios"
	}

	// Debug — default false, ParseBool syntax
	if v, ok := source("HELIOS_DEBUG"); ok {
		dbg, err := strconv.ParseBool(v)
		if err != nil {
			return Config{}, err
		}
		cfg.Debug = dbg
	} else {
		cfg.Debug = false
	}

	return cfg, nil
}