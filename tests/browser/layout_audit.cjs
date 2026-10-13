// Layout audit (0.9.4-beta.3): at common laptop and desktop sizes, with the timeline and the
// Free timeline at default, maximized and minimized heights, nothing important may be pushed
// out of view: no page scroll, header, Scene settings tabs, preview, narration and timeline
// toolbar all on screen with usable sizes. Usage: node layout_audit.cjs [baseUrl]
// (expects a running SceneForge with at least one project that has media).
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:8300';
const SIZES = [[1920, 1080], [1536, 864], [1366, 768], [1280, 720], [1100, 650]];
(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined});
  const problems = [];
  for (const [w, h] of SIZES) {
    const page = await browser.newPage({viewport: {width: w, height: h}});
    await page.route('**/api/local-ai/setup', r => r.fulfill({json: {status: 'idle', completed: 0, total: 0, current: '', log: [], error: '', supported: true, settings: {autostart: false, components: [], gpu: false}, running: {}}}));
    await page.goto(base); await page.waitForTimeout(800);
    await page.locator('.project-tile').first().click(); await page.waitForTimeout(2500);
    const skip = page.getByRole('button', {name: 'Skip tour', exact: true}); if (await skip.count()) await skip.click();
    if (await page.locator('.free-timeline').count()) {await page.getByRole('button', {name: /Scene assembly/}).first().click(); await page.waitForTimeout(600);}
    const audit = async (label) => {
      await page.waitForTimeout(500);
      const r = await page.evaluate(() => {
        const vis = sel => {const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect();
          return {top: Math.round(b.top), bottom: Math.round(b.bottom), left: Math.round(b.left), right: Math.round(b.right), h: Math.round(b.height), w: Math.round(b.width)};};
        return {scroll: document.scrollingElement.scrollHeight - innerHeight, hscroll: document.scrollingElement.scrollWidth - innerWidth,
          header: vis('.studio-toolbar'), tabs: vis('.scene-editor:not([hidden]) .inspector-tabs'), body: vis('.scene-editor:not([hidden]) .inspector-body'),
          preview: vis('.scene-editor:not([hidden]) .preview-canvas'), narration: vis('.scene-editor:not([hidden]) .script-card'),
          bar: vis('.sequence-toolbar') || vis('.free-timeline header'), vw: innerWidth, vh: innerHeight};
      });
      const bad = [];
      if (r.scroll > 1) bad.push(`page scrolls ${r.scroll}px`);
      if (r.hscroll > 1) bad.push(`page scrolls sideways ${r.hscroll}px`);
      const onScreen = (k, b, min) => {if (!b) return bad.push(`${k} missing`); if (b.top < -1 || b.bottom > r.vh + 1) bad.push(`${k} cut off (${b.top}–${b.bottom} of ${r.vh})`); if (min && b.h < min) bad.push(`${k} only ${b.h}px tall`);};
      onScreen('header', r.header); onScreen('settings tabs', r.tabs, 30); onScreen('settings content', r.body, label.includes('maximized') ? 60 : 140);
      onScreen('preview', r.preview, label.includes('maximized') ? 50 : 110); onScreen('narration', r.narration); onScreen('timeline toolbar', r.bar, 30);
      if (bad.length) problems.push(`${w}×${h} ${label}: ${bad.join('; ')}`);
      console.log(`${bad.length ? 'FAIL' : 'ok  '} ${w}×${h} ${label}${bad.length ? ' — ' + bad.join('; ') : ''}`);
    };
    for (const tab of ['Media', 'Effects', 'Text', 'Audio']) {await page.getByRole('tab', {name: tab, exact: true}).click(); await audit(`timeline default · ${tab}`);}
    await page.getByRole('button', {name: 'Maximize timeline'}).click(); await audit('timeline maximized');
    await page.getByRole('button', {name: 'Minimize or restore timeline'}).click(); await audit('timeline minimized');
    await page.getByRole('button', {name: 'Minimize or restore timeline'}).click(); await audit('timeline restored to maximized');
    await page.getByRole('button', {name: 'Free timeline · move clips anywhere'}).click(); await page.waitForTimeout(1200);
    const choice = page.locator('dialog.editor-choice'); if (await choice.count()) await choice.getByRole('button').first().click();
    await page.locator('.free-timeline').waitFor();
    await audit('free timeline default');
    await page.getByRole('button', {name: 'Maximize free timeline'}).click(); await audit('free timeline maximized');
    await page.getByRole('button', {name: /Restore free timeline/}).click();
    await page.getByRole('button', {name: 'Minimize free timeline'}).click(); await audit('free timeline minimized');
    await page.getByRole('button', {name: 'Restore minimized free timeline'}).click();
    await page.getByRole('button', {name: /Scene assembly/}).first().click(); await page.waitForTimeout(500);
    await page.close();
  }
  await browser.close();
  if (problems.length) {console.error(`\n${problems.length} layout problems`); process.exitCode = 1;}
  else console.log('\nPASS layout audit: every size and timeline state keeps tabs, preview, narration and timeline tools on screen');
})();
