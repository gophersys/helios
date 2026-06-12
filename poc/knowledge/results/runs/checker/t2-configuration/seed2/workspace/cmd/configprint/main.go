package main

import (
	"fmt"
	"os"

	"example.helios/configuration"
)

// envSource returns a Source that reads from the process environment.
func envSource(key string) (string, bool) {
	v, ok := os.LookupEnv(key)
	return v, ok
}

func main() {
	cfg, err := configuration.Load(envSource)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
}