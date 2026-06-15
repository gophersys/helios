package persistence

// Config and Deps are the idiomatic exported spine TYPE names — exempt (10 §5).
type Config struct{}

// Deps is the injected dependency record.
type Deps struct{}

// ObjectStore is a MEANINGFUL COMPOUND containing "Store" — allowed.
type ObjectStore interface {
	// Author is a MEANINGFUL COMPOUND interface method — allowed.
	Author() string
}

// DesiredStore is a MEANINGFUL COMPOUND — allowed.
type DesiredStore struct {
	// PostgresStore is a MEANINGFUL COMPOUND field — allowed.
	PostgresStore string
	// OAuth is a MEANINGFUL COMPOUND field — allowed.
	OAuth string
}

// TemplateStore is a MEANINGFUL COMPOUND func name — allowed.
func TemplateStore() *DesiredStore { return nil }
