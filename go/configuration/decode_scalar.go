package configuration

// stripSurroundingQuotes removes a single matched surrounding quote pair from s
// — a leading-and-trailing pair of the same quote rune, either double (") or
// single ('). An unmatched or absent pair is returned verbatim. This is the one
// home for the quote-strip rule shared by every decoder (YAML, TOML, and env),
// so the SAME literal `"v"` / `'v'` resolves to the SAME unquoted string value
// regardless of source Format — env previously took its value verbatim while
// YAML/TOML stripped, a silent cross-decoder divergence (cohesion: one concept,
// one home, 10 §9).
//
// It strips exactly ONE pair and only when both ends carry the same quote rune;
// it does not interpret escapes (the v1 decoders are byte-literal subsets), so
// "'v'" with mismatched ends, a lone leading quote, or the bare two-byte string
// `""` (handled by the len >= 2 guard returning "") behave predictably.
func stripSurroundingQuotes(s string) string {
	if len(s) >= 2 {
		first, last := s[0], s[len(s)-1]
		if (first == '"' && last == '"') || (first == '\'' && last == '\'') {
			return s[1 : len(s)-1]
		}
	}
	return s
}
