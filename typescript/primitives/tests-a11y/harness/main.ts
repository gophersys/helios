/** The a11y-evidence harness entry — inject Eden tokens, then mount the primitives under test. */
import { mount } from 'svelte';
import Harness from './Harness.svelte';
import { injectEdenTokens } from './theme.js';

injectEdenTokens();

const target = document.getElementById('harness');
if (!target) throw new Error('a11y harness: #harness mount target missing');

const app = mount(Harness, { target });
export default app;
