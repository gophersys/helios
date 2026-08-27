package codeinsight

// defaultViews is the producer-declared render-plan (contract §5): each entry names one of the
// @eden/visualization widget primitives, binds it to a Report collection + visual encoding, and tags
// the SDLC attention point it surfaces at. A frontend iterates this list and instantiates the named
// primitive — so adding a view is data, not code.
func defaultViews() []View {
	return []View{
		{
			ID:             "hotspots",
			Title:          "Hotspots — change frequency × complexity",
			Primitive:      "hotspot-map",
			AttentionPoint: "pull-request",
			Source:         "entities",
			Encoding: map[string]string{
				"x":     "churnRelative",
				"y":     "cyclomatic",
				"size":  "lines",
				"color": "hotspotScore",
				"label": "path",
			},
		},
		{
			ID:             "structure",
			Title:          "Codebase map — size & risk",
			Primitive:      "enclosure",
			AttentionPoint: "monitoring",
			Source:         "entities",
			Encoding: map[string]string{
				"size":  "lines",
				"color": "hotspotScore",
				"path":  "path",
			},
		},
		{
			ID:             "coupling",
			Title:          "Logical coupling — files that change together",
			Primitive:      "dependency-matrix",
			AttentionPoint: "release-gate",
			Source:         "couplings",
			Encoding: map[string]string{
				"rows":      "entityA",
				"columns":   "entityB",
				"intensity": "degree",
			},
		},
		{
			ID:             "ownership",
			Title:          "Knowledge map — ownership & bus factor",
			Primitive:      "ownership-map",
			AttentionPoint: "monitoring",
			Source:         "ownership",
			Encoding: map[string]string{
				"path":     "path",
				"color":    "primaryAuthor",
				"annotate": "busFactor",
			},
		},
		{
			ID:             "maintainability",
			Title:          "Maintainability rating",
			Primitive:      "rating-badge",
			AttentionPoint: "release-gate",
			Source:         "summary",
			Encoding: map[string]string{
				"grade": "maintainabilityRating",
				"value": "technicalDebtRatio",
			},
		},
		{
			ID:             "churn-trend",
			Title:          "Churn over time",
			Primitive:      "trend",
			AttentionPoint: "monitoring",
			Source:         "trends",
			Encoding: map[string]string{
				"x":     "at",
				"y":     "value",
				"label": "commit",
			},
		},
		{
			ID:             "entity-table",
			Title:          "All entities",
			Primitive:      "data-table",
			AttentionPoint: "pull-request",
			Source:         "entities",
			Encoding: map[string]string{
				"columns": "path,lines,cyclomatic,cognitive,maintainability,changeFrequency,hotspotScore,primaryAuthor",
				"sort":    "hotspotScore",
			},
		},
	}
}
