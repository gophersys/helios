/** The Wave-1 a11y-evidence harness entry — inject Eden tokens, then mount the atom/molecule set. */
import { mount } from 'svelte';
import Wave1Harness from './Wave1Harness.svelte';
import { injectEdenTokens } from './theme.js';

injectEdenTokens();

const target = document.getElementById('harness');
if (!target) throw new Error('wave1 a11y harness: #harness mount target missing');

const app = mount(Wave1Harness, { target });
export default app;
