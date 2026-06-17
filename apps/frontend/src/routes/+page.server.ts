// The root path is Eden's front door, and the front door is now the LOGIN screen (/login): a basic,
// pre-identity sign-in that loads the default user and continues into the Projects dashboard. Every
// entry point — the demo, a bare link, a bookmark — passes through login first. (The dashboard at
// /projects loads the identity lazily too, so a deep-link that skips login still works.)
import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = () => {
  redirect(307, '/login');
};
