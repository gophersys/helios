package agent

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// CredentialProvider is an interface for resolving API keys.
type CredentialProvider interface {
	// GetApiKey returns the API key for the given provider.
	GetApiKey(provider string) (string, bool)
	// ListProviders returns all known providers.
	ListProviders() []string
}

// EnvCredentialProvider resolves API keys from environment variables.
type EnvCredentialProvider struct{}

func (e *EnvCredentialProvider) GetApiKey(provider string) (string, bool) {
	envVar := strings.ToUpper(provider) + "_API_KEY"
	key := os.Getenv(envVar)
	if key != "" {
		return key, true
	}
	// Common aliases
	switch provider {
	case "openrouter":
		key = os.Getenv("OPENROUTER_API_KEY")
	case "anthropic":
		key = os.Getenv("ANTHROPIC_API_KEY")
	case "openai":
		key = os.Getenv("OPENAI_API_KEY")
	case "google":
		key = os.Getenv("GOOGLE_API_KEY")
	}
	return key, key != ""
}

func (e *EnvCredentialProvider) ListProviders() []string {
	var providers []string
	for _, env := range os.Environ() {
		if strings.HasSuffix(env, "_API_KEY") {
			parts := strings.SplitN(env, "=", 2)
			provider := strings.TrimSuffix(parts[0], "_API_KEY")
			providers = append(providers, strings.ToLower(provider))
		}
	}
	return providers
}

// FileCredentialProvider resolves API keys from a JSON file.
type FileCredentialProvider struct {
	keys map[string]string
}

// NewFileCredentialProvider loads credentials from a JSON file.
func NewFileCredentialProvider(path string) (*FileCredentialProvider, error) {
	provider := &FileCredentialProvider{
		keys: make(map[string]string),
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return provider, nil
		}
		return nil, fmt.Errorf("read credentials: %w", err)
	}
	// Support simple JSON format: {"provider_name": "api_key"}
	if err := parseCredentials(string(data), provider.keys); err != nil {
		return nil, fmt.Errorf("parse credentials: %w", err)
	}
	return provider, nil
}

func parseCredentials(data string, keys map[string]string) error {
	// Simple line-by-line provider=key format
	for _, line := range strings.Split(data, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "//") {
			continue
		}
		if parts := strings.SplitN(line, "=", 2); len(parts) == 2 {
			keys[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	return nil
}

func (f *FileCredentialProvider) GetApiKey(provider string) (string, bool) {
	key, ok := f.keys[strings.ToLower(provider)]
	return key, ok
}

func (f *FileCredentialProvider) ListProviders() []string {
	var providers []string
	for k := range f.keys {
		providers = append(providers, k)
	}
	return providers
}

// ChainCredentialProvider tries multiple providers in order.
type ChainCredentialProvider struct {
	providers []CredentialProvider
}

func NewChainCredentialProvider(providers ...CredentialProvider) *ChainCredentialProvider {
	return &ChainCredentialProvider{providers: providers}
}

func (c *ChainCredentialProvider) GetApiKey(provider string) (string, bool) {
	for _, p := range c.providers {
		if key, ok := p.GetApiKey(provider); ok {
			return key, ok
		}
	}
	return "", false
}

func (c *ChainCredentialProvider) ListProviders() []string {
	seen := make(map[string]bool)
	var result []string
	for _, p := range c.providers {
		for _, prov := range p.ListProviders() {
			if !seen[prov] {
				seen[prov] = true
				result = append(result, prov)
			}
		}
	}
	return result
}

// OMPCredentialsPath returns the OMP agent credential directory.
func OMPCredentialsPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".omp", "agent")
}

// DiscoverOMPCredentials tries to find valid credentials from the OMP installation.
func DiscoverOMPCredentials() (*ChainCredentialProvider, error) {
	providers := []CredentialProvider{
		&EnvCredentialProvider{},
	}

	// Try OMP credential file
	ompDir := OMPCredentialsPath()
	if ompDir != "" {
		// Try agent.db or similar
		credPath := filepath.Join(ompDir, "credentials.json")
		if fp, err := NewFileCredentialProvider(credPath); err == nil {
			providers = append(providers, fp)
		}

		// Try inline credential format
		for _, fname := range []string{".env", "models.yml", "config.yml"} {
			fpath := filepath.Join(ompDir, fname)
			if fip, err := NewFileCredentialProvider(fpath); err == nil {
				providers = append(providers, fip)
			}
		}
	}

	return NewChainCredentialProvider(providers...), nil
}

// SetupOMPCredentials writes provider credentials into a format OMP can read.
// Returns the path to the written credential file.
func SetupOMPCredentials(credsDir string, provider string, apiKey string) (string, error) {
	if err := os.MkdirAll(credsDir, 0755); err != nil {
		return "", fmt.Errorf("mkdir creds: %w", err)
	}

	// Write as environment file that OMP can source
	envFile := filepath.Join(credsDir, ".env")
	envVar := strings.ToUpper(provider) + "_API_KEY"
	content := fmt.Sprintf("%s=%s\n", envVar, apiKey)

	// Append to existing
	existing, err := os.ReadFile(envFile)
	if err != nil {
		if !os.IsNotExist(err) {
			return "", fmt.Errorf("read existing env file: %w", err)
		}
		// File doesn't exist, start fresh
	} else {
		lines := strings.Split(string(existing), "\n")
		found := false
		for i, line := range lines {
			if strings.HasPrefix(line, envVar+"=") {
				lines[i] = envVar + "=" + apiKey
				found = true
				break
			}
		}
		if found {
			content = strings.Join(lines, "\n")
		} else {
			content = string(existing) + "\n" + content
		}
	}

	return envFile, os.WriteFile(envFile, []byte(content), 0600)
}