// Owner remarks on 0.9.4-beta.3 (local test): the NVIDIA option must stay ticked, the timeline
// edit tools must say what they do (and Blade must cut parts on the Picture track), media can
// be inserted between two parts with a visible "Insert as a new part here" marker or from the
// right-click menu, and a part without narration shows the "narration first" tip in Motion,
// Effects and Text. Usage: node owner_beta4.cjs [baseUrl] (expects a project with 3 parts that
// have media, like tests/browser fixtures; no paid calls, no downloads).
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:8300';
const api = async (u, b, m = 'POST') => {const r = await fetch(base + '/api' + u, {method: m, headers: {'content-type': 'application/json'}, body: b === undefined ? undefined : JSON.stringify(b)}); if (!r.ok) throw Error(u + ' ' + await r.text()); return r.json();};
(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined});
  const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  // A fresh project: a picture part without narration and a video part.
  const fs = require('fs'), path = require('path');
  const up = async (pid, f) => {const fd = new FormData(); fd.append('file', new Blob([fs.readFileSync(f)]), path.basename(f)); return (await fetch(base + '/api/assets/upload?project_id=' + pid, {method: 'POST', body: fd})).json();};
  const root = path.resolve(__dirname, '../..');
  let p = await api('/projects', {title: 'Beta4 owner checks', aspect: '16:9'}); p = await api('/projects/' + p.id, undefined, 'GET');
  const clip = await up(p.id, path.join(root, 'examples/fixture_assets/clip1.mp4'));
  for (const s of p.scenes.slice(0, 2)) await api('/scenes/' + s.id + '/shots', {asset_id: clip.id});
  await api('/scenes/' + p.scenes[2].id, undefined, 'DELETE').catch(() => {});

  await page.goto(base); await page.getByRole('button', {name: /Beta4 owner checks/}).first().click(); await page.waitForTimeout(2500);
  const skip = page.getByRole('button', {name: 'Skip tour', exact: true}); if (await skip.count()) await skip.click();

  // 1. Narration-first tip.
  for (const tab of ['Motion', 'Effects', 'Text']) {
    await page.getByRole('tab', {name: tab, exact: true}).click();
    assert(await page.locator('.scene-editor:not([hidden]) .order-tip').isVisible(), tab + ' shows the narration-first tip');
  }
  await page.locator('.scene-editor:not([hidden]) .order-tip').getByRole('button', {name: 'Go to Voice & narration'}).click();
  assert.equal(await page.getByRole('tab', {name: 'Audio', exact: true}).getAttribute('aria-selected'), 'true');
  console.log('PASS a part without narration says to add narration first and links to Voice & narration');

  // 2. Edit tools explain themselves; Blade cuts a part on the Picture track where clicked.
  await page.getByRole('button', {name: 'Slip tool'}).click();
  assert.match(await page.locator('.tool-feedback').textContent(), /Slip: .*A3–A8.*Add music or a sound effect/);
  await page.getByRole('button', {name: 'Blade tool'}).click();
  assert.match(await page.locator('.tool-feedback').textContent(), /Blade: click a part on the Picture track/);
  const before = (await api('/projects/' + p.id, undefined, 'GET')).scenes.length;
  const first = page.locator('.picture-clip').first(); await first.scrollIntoViewIfNeeded(); const fb = await first.boundingBox();
  await first.click({position: {x: fb.width / 2, y: 30}}); await page.waitForTimeout(500);
  const confirm = page.locator('dialog[open]'); if (await confirm.count()) await confirm.getByRole('button').last().click();
  for (let i = 0; i < 40 && (await api('/projects/' + p.id, undefined, 'GET')).scenes.length === before; i++) await page.waitForTimeout(250);
  assert.equal((await api('/projects/' + p.id, undefined, 'GET')).scenes.length, before + 1, 'Blade split the clicked part in two');
  await page.getByRole('button', {name: 'Select tool'}).click();
  console.log('PASS edit tools say what they do; Blade cuts a Picture-track part where it is clicked');

  // 3. Insert between parts: marker while dragging, and the right-click menu.
  await page.getByText('Media Pool', {exact: true}).first().click(); await page.waitForTimeout(400);
  const tile = page.locator('.pool-grid article').first();
  const second = page.locator('.picture-clip').nth(1); const sb = await second.boundingBox();
  const dt = await page.evaluateHandle(() => new DataTransfer());
  await tile.dispatchEvent('dragstart', {dataTransfer: dt});
  await second.dispatchEvent('dragover', {dataTransfer: dt, clientX: sb.x + 4, clientY: sb.y + sb.height / 2});
  assert.equal(await second.getAttribute('data-drop-label'), 'Insert as a new part here');
  assert(/drop-before/.test(await second.getAttribute('class')));
  await second.dispatchEvent('dragover', {dataTransfer: dt, clientX: sb.x + sb.width / 2, clientY: sb.y + sb.height / 2});
  assert.match(await second.getAttribute('data-drop-label'), /^Add to /);
  const n = (await api('/projects/' + p.id, undefined, 'GET')).scenes.length;
  await second.dispatchEvent('drop', {dataTransfer: dt, clientX: sb.x + 4, clientY: sb.y + sb.height / 2});
  for (let i = 0; i < 40 && (await api('/projects/' + p.id, undefined, 'GET')).scenes.length === n; i++) await page.waitForTimeout(250);
  const after = await api('/projects/' + p.id, undefined, 'GET');
  assert.equal(after.scenes.length, n + 1, 'dropping at the edge inserted a new part');
  await page.locator('.picture-clip').first().click({button: 'right'});
  assert.deepEqual(await page.getByRole('menuitem', {name: /Insert picture or video/}).allTextContents(), ['Insert picture or video before…', 'Insert picture or video after…']);
  await page.keyboard.press('Escape');
  console.log('PASS media dropped between two parts becomes a new part, with a visible marker; right-click offers Insert before/after');

  // 4. The NVIDIA option stays ticked (saved), also after reopening.
  await page.getByRole('button', {name: 'AI Engines', exact: true}).click();
  await page.getByRole('button', {name: 'Local image engines'}).click();
  const gpu = page.getByLabel('Use my NVIDIA graphics card'); await gpu.waitFor();
  const was = await gpu.isChecked(); await gpu.click(); await page.waitForTimeout(3500);   // past one status poll
  assert.equal(await gpu.isChecked(), !was);
  assert.equal((await api('/local-ai/setup', undefined, 'GET')).settings.gpu, !was);
  await page.reload(); await page.waitForTimeout(1500);
  if (await page.getByRole('button', {name: /Beta4 owner checks/}).count()) await page.getByRole('button', {name: /Beta4 owner checks/}).first().click();
  await page.waitForTimeout(1500);
  await page.getByRole('button', {name: 'AI Engines', exact: true}).click();
  await page.getByRole('button', {name: 'Local image engines'}).click();
  assert.equal(await page.getByLabel('Use my NVIDIA graphics card').isChecked(), !was);
  await page.getByLabel('Use my NVIDIA graphics card').click(); await page.waitForTimeout(800);   // restore
  console.log('PASS the NVIDIA graphics card option stays ticked after the status refresh and after reopening');
  assert.equal(errors.length, 0, errors.join('\n'));
  await browser.close();
})().catch(e => {console.error(e); process.exit(1);});
