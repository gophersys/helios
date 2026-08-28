/** The WizardShell a11y-evidence harness entry — inject Eden tokens, then mount the wizard organism. */
import { mount } from 'svelte';
import WizardShellHarness from './WizardShellHarness.svelte';
import { injectEdenTokens } from './theme.js';

injectEdenTokens();

const target = document.getElementById('harness');
if (!target) throw new Error('wizard-shell a11y harness: #harness mount target missing');

const app = mount(WizardShellHarness, { target });
export default app;
