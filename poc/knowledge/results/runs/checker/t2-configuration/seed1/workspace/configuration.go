package configuration

import (
	"strconv"
)

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

// Config holds the loaded application configuration.
type Config struct {
	Port  int
	Name  string
	Debug bool
}

// Load reads configuration keys from source and returns a parsed Config.
func Load(source Source) (Config, error) {
	cfg := Config{
		Port:  8080,
		Name:  "helios",
		Debug: false,
	}

	if v, ok := source("HELIOS_PORT"); ok {
		p, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, &strconv.NumError{Func: "Atoi", Num: v, Err: err}
		}
		if p < 1 || p > 65535 {
			return Config{}, &strconv.NumError{
				Func: "Atoi",
				Num:  v,
				Err:  strconv.ErrRange,
			}
		}
		cfg.Port = p
	}

	if v, ok := source("HELIOS_NAME"); ok {
		if v == "" {
			return Config{}, &emptyNameError{}
		}
		cfg.Name = v
	}

	if v, ok := source("HELIOS_DEBUG"); ok {
		d, err := strconv.ParseBool(v)
		if err != nil {
			return Config{}, err
		}
		cfg.Debug = d
	}

	return cfg, nil
}

// emptyNameError is returned when HELIOS_NAME is present but empty.
type emptyNameError struct{}

func (e *emptyNameError) Error() string {
	return "HELIOS_NAME must not be empty"
}