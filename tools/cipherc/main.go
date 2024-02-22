package main

import (
	"flag"
	"fmt"
	"log"
	"path/filepath"

	generator "corekinect/concord/tools/cipherc/src"
)

func main() {
	// Get input parameters
	var language, protoFile, outputPath string
	flag.StringVar(&language, "language", "", "Programming language for the generated files.")
	flag.StringVar(&protoFile, "proto", "", "Protobuf file to generate files from.")
	flag.StringVar(&outputPath, "out", "", "Output folder for the generated files.")
	flag.Parse()

	// Check input parameters
	if language == "" {
		log.Fatal("Please specify a programming language with the -language flag.")
	}

	if protoFile == "" {
		log.Fatal("Please specify a .proto file -proto flag.")
	}

	if outputPath == "" {
		log.Fatal("Please specify an output path using the -out flag.")
	}

	absOutputPath, err := filepath.Abs(outputPath)
	if err != nil {
		log.Fatalf("Error determining absolute path of output folder: %v", err)
	}

	fmt.Printf("Generating %s files in %s\n", language, absOutputPath)

	if err := generator.Generate(language, protoFile, absOutputPath); err != nil {
		log.Fatalf("Error generating files: %v", err)
	}
}
