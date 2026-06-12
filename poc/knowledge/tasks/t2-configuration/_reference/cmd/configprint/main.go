// configprint is the composition root: the only place the process
// environment is read.
package main

import (
	"fmt"
	"os"

	configuration "example.helios/configuration"
)

func main() {
	cfg, err := configuration.Load(func(key string) (string, bool) {
		return os.LookupEnv(key)
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
}
