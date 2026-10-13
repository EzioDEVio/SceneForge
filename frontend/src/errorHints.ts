/** Plain-language "what to do next" for errors (0.9.4-beta.4). The original message is always
 *  still shown; this only adds the next step, it never hides or replaces the error. */
const RULES: [RegExp, string][] = [
  [/no narration|write narration|narration first|no voice take|voice take|nothing to transcribe|no .*audio .*transcribe/i,
    'Add the narration for this part first (Audio → Voice & narration: generate a voice or upload a recording). Effects, motion and captions are kept and follow the narration’s length.'],
  [/render (this|the) scene first|render it (first|before)/i,
    'Click Render scene above the narration, wait for “Scene ready”, then try again.'],
  [/not running|not answering|unavailable|connection (refused|reset)|failed to fetch|networkerror/i,
    'The engine or SceneForge’s background service is not answering. Open AI Engines and click Start (or restart SceneForge), then try again.'],
  [/no such file|file is missing|missing from|not found on disk|could not open|does not exist/i,
    'A media file this part uses has moved or been deleted. Re-import it from Media Pool or replace it in Media, then render again.'],
  [/error while filtering|filtergraph|invalid argument|conversion failed|ffmpeg|exit status|returned non-zero/i,
    'One of this part’s effect, motion or text settings could not be rendered. Undo the last change (Ctrl+Z) and render again; then add it back one setting at a time. If it still fails, open the details and send them to us.'],
  [/out of memory|cuda error|memoryerror/i,
    'The computer ran out of memory. Close other programs, choose a smaller export size, or turn off the graphics-card option in AI Engines, then retry.'],
  [/no space left|disk is full|not enough free space/i, 'The disk is full. Free some space, then retry.'],
];

export function errorHint(message?: string | null): string {
  if (!message) return '';
  for (const [pattern, hint] of RULES) if (pattern.test(message)) return hint;
  return '';
}
