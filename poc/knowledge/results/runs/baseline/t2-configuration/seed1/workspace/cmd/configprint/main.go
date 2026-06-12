package main

import (
	"fmt"
	"os"

	"example.helios/configuration"
)

func main() {
	cfg, err := configuration.Load(configuration.Source(os.LookupEnv))
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
}