package identity

// Auth is a BARE banned exported type name — it must be flagged (use Identity).
type Auth struct {
	// Repo is a BARE banned exported field name — it must be flagged.
	Repo string
	// ObjectStore is a MEANINGFUL COMPOUND — it must NOT be flagged.
	ObjectStore string
}

// Store is a BARE banned exported method name — it must be flagged.
func (a Auth) Store() string { return a.Repo }

// Author is a MEANINGFUL COMPOUND func name — it must NOT be flagged.
func Author() string { return "" }
