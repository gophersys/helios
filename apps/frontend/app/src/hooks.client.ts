import type { HandleClientError } from '@sveltejs/kit';
import { reportJsError } from '$lib/stores/error-reporter.svelte';

const STALE_CHUNK_RE = /Failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed/i;

export const handleError: HandleClientError = ({ error, message }) => {
	const err = error as Error;
	const msg = err?.message || message;

	if (STALE_CHUNK_RE.test(msg)) {
		const key = 'concord:chunk-reload';
		const last = sessionStorage.getItem(key);
		if (!last || Date.now() - Number(last) > 10_000) {
			sessionStorage.setItem(key, String(Date.now()));
			location.reload();
			return { message: 'Updating application…' };
		}
	}

	reportJsError({
		message: msg,
		stack: err?.stack,
	});

	console.error('[handleError]', err);

	return { message: msg };
};
