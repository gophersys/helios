/** Maps stage names to CSS class names for consistent coloring. */
const STAGE_MAP: Record<string, string> = {
	'completeness': 'stage-completeness',
	'ai-review-completeness': 'stage-completeness',
	'security': 'stage-security',
	'ai-review-security': 'stage-security',
	'blast-radius': 'stage-blast-radius',
	'ai-review-blast-radius': 'stage-blast-radius',
	'docs': 'stage-docs',
	'ai-review-docs': 'stage-docs',
	'architecture': 'stage-architecture',
	'ai-review-architecture': 'stage-architecture',
	'proto-sync': 'stage-proto-sync',
	'serializer-check': 'stage-serializer',
	'types-sync': 'stage-serializer',
};

export function stageClass(name: string): string {
	return STAGE_MAP[name] || 'stage-default';
}

export function stageName(raw: string): string {
	return raw
		.replace(/^ai-review-/, '')
		.replace(/-/g, ' ')
		.replace(/\b\w/g, c => c.toUpperCase());
}
