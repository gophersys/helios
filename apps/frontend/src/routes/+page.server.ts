// The root path is Eden's front door, and the front door is the Projects dashboard (/projects):
// a grid of what the user is building, with the "＋ New project" creation flow. The legacy
// document-workspace grid that used to live here is retired (its workspace pages remain under
// /p/[slug]); the root now redirects so every entry point — the demo, a bare link, a bookmark —
// lands on the projects home.
import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = () => {
  redirect(307, '/projects');
};
