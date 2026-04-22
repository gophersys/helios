import { json } from '@sveltejs/kit';
import { getTrends } from '$lib/server/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url }) => {
	const days = parseInt(url.searchParams.get('days') || '14');
	const trends = getTrends(days);
	return json({ data: trends });
};
