import { defineConfig } from 'histoire';
import { HstSvelte } from '@histoire/plugin-svelte';

export default defineConfig({
  plugins: [HstSvelte()],
  setupFile: './src/histoire-setup.ts',
  storyMatch: ['./src/**/*.story.svelte'],
  tree: {
    groups: [
      { id: 'ui', title: 'UI Components' },
      { id: 'products', title: 'Products' },
      { id: 'fixtures', title: 'Fixtures' },
      { id: 'manufacturing', title: 'Manufacturing' },
    ],
  },
  theme: {
    title: 'Concord UI',
  },
});
