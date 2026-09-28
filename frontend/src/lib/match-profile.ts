// Search terms describe the owner's target work, not a verified list of mastered tools.
export const MATCH_PROFILE = [
  'AI video generation', 'text to video', 'image to video', 'video to video', 'AI filmmaking',
  'generative video', 'AI video creator', 'AI video artist', 'AI video producer', 'AI animation',
  'cinematic AI video', 'AI commercials', 'AI ads', 'AI product videos', 'AI music videos',
  'AI UGC', 'virtual production', 'AI storytelling', 'AI storyboarding', 'video prompting',
  'motion prompting', 'camera motion control', 'character consistency', 'scene consistency', 'lip sync',
  'talking avatars', 'digital humans', 'AI avatar video', 'video upscaling', 'frame interpolation',
  'ComfyUI', 'ComfyUI workflows', 'custom nodes', 'node based workflows', 'FLUX',
  'FLUX.1', 'FLUX Kontext', 'Stable Diffusion', 'SDXL', 'SD 3.5',
  'LoRA', 'LoRA training', 'FLUX LoRA', 'character LoRA', 'style LoRA',
  'model fine tuning', 'dataset curation', 'image captioning', 'training captions', 'synthetic datasets',
  'ControlNet', 'IP-Adapter', 'reference images', 'pose control', 'depth maps',
  'inpainting', 'outpainting', 'img2img', 'txt2img', 'image upscaling',
  'AI image generation', 'generative imagery', 'AI art direction', 'AI product photography', 'AI portraits',
  'consistent characters', 'consistent products', 'photorealistic AI', 'stylized AI', 'concept art',
  'Kling', 'Runway', 'Pika', 'Luma Dream Machine', 'Hailuo',
  'Veo', 'Sora', 'Wan', 'HunyuanVideo', 'AnimateDiff',
  'generative AI', 'prompt engineering', 'visual prompting', 'negative prompts', 'prompt workflows',
  'AI creative workflow', 'workflow optimization', 'batch generation', 'API generation', 'Python scripting',
  'AI content creation', 'creative automation', 'AI video editing', 'post production', 'color grading',
  'sound design', 'voice generation', 'AI voiceover', 'subtitles', 'short form AI content',
] as const;

// These terms identify the niche on their own. Broad production terms only support a match.
const CORE_TERMS = new Set<string>([...MATCH_PROFILE.slice(0, 20), ...MATCH_PROFILE.slice(30, 81)]);
const normalize = (text: string) => ` ${text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').replace(/\s+/g, ' ').trim()} `;
const hasTerm = (text: string, term: string) => text.includes(normalize(term));

export function matchJob(job: Record<string, unknown>) {
  const title = normalize(String(job.title || job.job_title || ''));
  const description = normalize(String(job.description || job.job_description || job.body || ''));
  const matched = MATCH_PROFILE.filter(term => hasTerm(title, term) || hasTerm(description, term));
  const core = matched.filter(term => CORE_TERMS.has(term) && !matched.some(other => other !== term && CORE_TERMS.has(other) && normalize(other).includes(normalize(term))));
  const coreInTitle = core.some(term => hasTerm(title, term));
  return {
    perfect_match: coreInTitle || core.length >= 2,
    match_terms: matched.slice(0, 12),
  };
}
