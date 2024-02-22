package generator

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"text/template"

	"github.com/emicklei/proto"
)

type ServiceData struct {
	Services []ServiceInfo
}

type ServiceInfo struct {
	ServiceName          string
	ServiceNameLowerCase string
	ProtoFileName        string
	ServiceID            int
	RPCs                 []RPCInfo
}

type RPCInfo struct {
	ServiceName string
	ID          int
	Name        string
	RequestType string
	ReturnsType string
}

var protoFileName string
var serviceData ServiceData

func Generate(language, protoFile, outputPath string) error {
	baseName := filepath.Base(protoFile)
	protoFileName = strings.TrimSuffix(baseName, filepath.Ext(baseName))

	// Open the proto file
	reader, err := os.Open(protoFile)
	if err != nil {
		log.Fatalf("Error opening proto file: %v", err)
	}
	defer reader.Close()

	// Parse the proto file
	parser := proto.NewParser(reader)
	definition, err := parser.Parse()
	if err != nil {
		log.Fatalf("Error parsing proto file: %v", err)
	}

	// Walk through the parsed proto definition to fill in serviceData
	proto.Walk(definition, proto.WithService(handleService), proto.WithRPC(handleRPC))

	// Ensure the output directory exists
	if err := os.MkdirAll(outputPath, 0755); err != nil {
		return err
	}

	// Generate the source file
	for _, service := range serviceData.Services {

		if language == "c" {
			// Generate the source file
			sourceFileName := fmt.Sprintf("%s.cipher.c", protoFileName)
			sourceTmplPath := filepath.Join("/workspaces/concord/tools/cipherc/src/templates", "c_source.tmpl")
			if err := executeTemplate(service, sourceTmplPath, outputPath, sourceFileName); err != nil {
				log.Fatalf("Error executing source template for service %s: %v", service.ServiceName, err)
			}

			// Generate the header file
			headerFileName := fmt.Sprintf("%s.cipher.h", protoFileName)
			headerTmplPath := filepath.Join("/workspaces/concord/tools/cipherc/src/templates", "c_header.tmpl")
			if err := executeTemplate(service, headerTmplPath, outputPath, headerFileName); err != nil {
				log.Fatalf("Error executing header template for service %s: %v", service.ServiceName, err)
			}
		} else if language == "python" {
			// Generate the source file
			pythonFileName := fmt.Sprintf("%s_cipher.py", replaceHyphens(protoFileName)+"_pb2")
			pythonTmplPath := filepath.Join("/workspaces/concord/tools/cipherc/src/templates", "python.tmpl")
			if err := executeTemplate(service, pythonTmplPath, outputPath, pythonFileName); err != nil {
				log.Fatalf("Error executing source template for service %s: %v", service.ServiceName, err)
			}
		} else {
			log.Fatalf("Unknown language option: %v", language)
		}

	}

	return nil
}

func replaceHyphens(input string) string {
	return strings.ReplaceAll(input, "-", "_")
}

func executeTemplate(service ServiceInfo, tmplPath, outputPath, fileName string) error {
	// Ensure funcMap is defined as before with "ToUpper" and any other needed functions
	funcMap := template.FuncMap{
		"ToUpper":        strings.ToUpper,
		"ToLower":        strings.ToLower,
		"replaceHyphens": replaceHyphens,
	}

	// Load and parse the template with FuncMap
	tmpl, err := template.New(filepath.Base(tmplPath)).Funcs(funcMap).ParseFiles(tmplPath)
	if err != nil {
		return fmt.Errorf("error parsing template: %v", err)
	}

	// Create the output file
	outputFile := filepath.Join(outputPath, fileName)
	f, err := os.Create(outputFile)
	if err != nil {
		return fmt.Errorf("error creating output file: %v", err)
	}
	defer f.Close()

	// Execute the template with service data
	if err := tmpl.Execute(f, service); err != nil {
		return fmt.Errorf("error executing template: %v", err)
	}

	return nil
}

var ServiceName string

func handleService(s *proto.Service) {
	// Example of setting ServiceNameLowerCase and ServiceID
	ServiceName = s.Name
	serviceInfo := ServiceInfo{
		ServiceName:          s.Name,
		ServiceNameLowerCase: strings.ToLower(s.Name),
		ProtoFileName:        protoFileName,                 // Assume protoFile is the path to the proto file
		ServiceID:            len(serviceData.Services) + 1, // Example sequential ID
	}
	serviceData.Services = append(serviceData.Services, serviceInfo)
}

func handleRPC(r *proto.RPC) {
	// Similar to before, find the correct service and append RPC info
	if len(serviceData.Services) > 0 {
		service := &serviceData.Services[len(serviceData.Services)-1]
		rpcInfo := RPCInfo{
			ServiceName: ServiceName,
			Name:        r.Name,
			RequestType: r.RequestType,
			ReturnsType: r.ReturnsType,
			ID:          len(service.RPCs) + 1, // Example sequential ID
		}
		service.RPCs = append(service.RPCs, rpcInfo)
	}
}
