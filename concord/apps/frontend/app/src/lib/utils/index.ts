/**
 * Centralized utilities - import from '$lib/utils' for convenience.
 */

// Formatting utilities
export * from './formatting';

// Collection utilities (groupBy, sortBy, etc.)
export * from './collections';

// Transition presets
export * from './transitions';

// Class merging (shadcn-svelte pattern)
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}
