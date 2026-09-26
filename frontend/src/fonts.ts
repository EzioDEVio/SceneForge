// Mirrors backend/app/render/fontruns.py so the editor preview picks the same
// font per script as the renderer: Arabic letters use an Arabic family, all
// other characters use a Latin family. The Arabic @font-face rules are limited
// to Arabic code points (unicode-range), so Latin text falls through to the
// Latin family exactly as it does in the burned-in output.
export const ARABIC_FAMILIES = ['Noto Naskh Arabic', 'Noto Sans Arabic', 'Amiri', 'Tajawal', 'Lalezar'];
const OWN_LATIN = ['Amiri', 'Tajawal', 'Lalezar'];
const ARABIC_PARTNER: Record<string, string> = {'Poppins': 'Tajawal', 'Bebas Neue': 'Lalezar', 'Anton': 'Lalezar', 'Pacifico': 'Amiri'};
export const BUNDLED_FAMILIES = ['Noto Sans', 'Poppins', 'Bebas Neue', 'Anton', 'Pacifico', 'Noto Naskh Arabic', 'Noto Sans Arabic', 'Amiri', 'Tajawal', 'Lalezar'];
const SERIF_LATIN = ['Times New Roman', 'Georgia'];

export function fontPair(family?: string): [arabic: string, latin: string] {
  const f = (family || ARABIC_FAMILIES[0]).trim();
  if (ARABIC_FAMILIES.includes(f)) return [f, OWN_LATIN.includes(f) ? f : 'Noto Sans'];
  if (ARABIC_PARTNER[f]) return [ARABIC_PARTNER[f], f];
  return [SERIF_LATIN.includes(f) ? 'Noto Naskh Arabic' : 'Noto Sans Arabic', f];
}

export function previewFontFamily(family?: string): string {
  const [arabic, latin] = fontPair(family);
  return `'${arabic}', '${latin}', sans-serif`;
}
