// Each mounted editor registers its current save operation. Nothing here can
// authorize application exit; the desktop main process owns that decision.
const savers = new Map<string, () => Promise<boolean>>();
export function registerCloseSave(id: string, save: () => Promise<boolean>) {
  savers.set(id, save);
  return () => { savers.delete(id); };
}
export async function saveBeforeClose(): Promise<boolean> {
  (document.activeElement as HTMLElement | null)?.blur?.();
  for (const save of [...savers.values()]) {
    try { if (!(await save())) return false; } catch { return false; }
  }
  return true;
}
