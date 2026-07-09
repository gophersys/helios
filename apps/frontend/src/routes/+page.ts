// The root path is Eden's front door, and the front door is now the LOGIN screen (/login): a basic,
// pre-identity sign-in that loads the default user and continues into the Projects dashboard. Every
// entry point — the demo, a bare link, a bookmark — passes through login first. UNIVERSAL load
// (not server): the deployed frontend is adapter-static (no SSR server), so the redirect must run
// client-side — the server variant 500'd the bare / on the home cluster (proven live). (The dashboard at
// /projects loads the identity lazily too, so a deep-link that skips login still works.)
import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = () => {
  redirect(307, '/login');
};
