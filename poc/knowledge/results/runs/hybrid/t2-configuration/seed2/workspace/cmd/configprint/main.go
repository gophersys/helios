package main

import (
	"fmt"
	"os"

	"example.helios/configuration"
)

func main() {
	source := func(key string) (string, bool) {
		v, ok := os.LookupEnv(key)
		return v, ok
	}

	cfg, err := configuration.Load(source)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
}