/** The form-action a11y-evidence harness entry — inject Eden tokens, then mount the form group. */
import { mount } from 'svelte';
import FormHarness from './FormHarness.svelte';
import { injectEdenTokens } from './theme.js';

injectEdenTokens();

const target = document.getElementById('harness');
if (!target) throw new Error('form a11y harness: #harness mount target missing');

const app = mount(FormHarness, { target });
export default app;
