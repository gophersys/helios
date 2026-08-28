/** The SettingsSurface a11y-evidence harness entry — inject Eden tokens, then mount the sheet organism. */
import { mount } from 'svelte';
import SettingsSurfaceHarness from './SettingsSurfaceHarness.svelte';
import { injectEdenTokens } from './theme.js';

injectEdenTokens();

const target = document.getElementById('harness');
if (!target) throw new Error('settings-surface a11y harness: #harness mount target missing');

const app = mount(SettingsSurfaceHarness, { target });
export default app;
