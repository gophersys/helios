package main

import (
	"fmt"
	"os"

	"example.helios/configuration"
)

func main() {
	cfg, err := configuration.Load(func(key string) (string, bool) {
		v := os.Getenv(key)
		return v, v != ""
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
}