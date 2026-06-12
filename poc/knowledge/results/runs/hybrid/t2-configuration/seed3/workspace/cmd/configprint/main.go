package main

import (
	"fmt"
	"os"

	"example.helios/configuration"
)

func main() {
	source := func(key string) (string, bool) {
		return os.LookupEnv(key)
	}
	cfg, err := configuration.Load(source)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
}