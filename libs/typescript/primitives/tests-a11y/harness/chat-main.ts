/** The chat-group a11y-evidence harness entry — inject Eden tokens, then mount the chat surfaces. */
import { mount } from 'svelte';
import ChatHarness from './ChatHarness.svelte';
import { injectEdenTokens } from './theme.js';

injectEdenTokens();

const target = document.getElementById('harness');
if (!target) throw new Error('chat a11y harness: #harness mount target missing');

const app = mount(ChatHarness, { target });
export default app;
