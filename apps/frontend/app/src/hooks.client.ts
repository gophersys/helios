import type { HandleClientError } from '@sveltejs/kit';

export const handleError: HandleClientError = ({ error, message }) => {
	const err = error as Error;

	// In dev/staging, inject a persistent error overlay into the DOM
	const env = document.querySelector('meta[name="app-environment"]')?.getAttribute('content') || 'development';
	if (env !== 'production') {
		// Remove existing overlay if any
		document.getElementById('__dev_error_overlay')?.remove();

		const overlay = document.createElement('div');
		overlay.id = '__dev_error_overlay';
		overlay.style.cssText = 'position:fixed;bottom:16px;right:16px;left:16px;z-index:99999;max-width:600px;margin-left:auto;font-family:monospace;';
		overlay.innerHTML = `
			<div style="background:#1a1a2e;border:2px solid #e74c3c;border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.5);">
				<div style="background:#e74c3c;padding:6px 12px;display:flex;justify-content:space-between;align-items:center;">
					<span style="color:white;font-size:12px;font-weight:bold;">⚠ Runtime Error</span>
					<button onclick="this.closest('#__dev_error_overlay').remove()" style="color:white;background:none;border:none;cursor:pointer;font-size:14px;">✕</button>
				</div>
				<div style="padding:12px;max-height:300px;overflow:auto;">
					<p style="color:#e74c3c;font-size:14px;margin:0 0 8px 0;font-weight:600;">${err?.message || message}</p>
					<pre style="color:#888;font-size:11px;white-space:pre-wrap;margin:0;">${err?.stack || ''}</pre>
				</div>
			</div>
		`;
		document.body.appendChild(overlay);
	}

	console.error('[handleError]', err);

	return {
		message: err?.message || message,
	};
};
