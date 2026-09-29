import taxonomy from './niches.json';

export const NICHES = taxonomy;
export const validNicheIds = new Set<string>(NICHES.map(niche => niche.id));
export type Preference = { niches: string[]; keywords: string[] };

export function customerMatch(job: Record<string, unknown>, preferences: Preference) {
  const scores = (job.niche_scores && typeof job.niche_scores === 'object') ? job.niche_scores as Record<string, number> : {};
  const selected = preferences.niches.filter(id => Number(scores[id]) > 0);
  const score = Math.max(0, ...selected.map(id => Number(scores[id])));
  const terms = Array.isArray(job.normalized_tags) ? job.normalized_tags.filter((term): term is string => typeof term === 'string') : [];
  return { match_score: score, match_terms: terms.slice(0, 10), matched_niches: selected };
}
