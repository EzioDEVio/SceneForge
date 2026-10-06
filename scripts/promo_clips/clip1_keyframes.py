import sys; sys.path.insert(0,'.')
from rec import *
import reset
reset.no_markers(); reset.golden_title()
PX=150  # timeline px per second
with Rec('1_keyframes') as r:
    ed, pg = r.ed, r.pg
    ed.open(inspector=560); ed.dock(700); ed.zoom(PX); ed.scene('Golden hour'); ed.tab('Text')
    pg.get_by_role('button', name='Preview', exact=True).first.click(); pg.wait_for_timeout(1200)
    ed.scroll_to('Text overlays', 10); pg.wait_for_timeout(400)
    ruler = pg.locator('.sequence-ruler'); rb = ruler.bounding_box()
    x0 = rb['x']; ry = rb['y'] + rb['height']/2
    at = lambda s: x0 + 2 + s*PX
    body = pg.locator('.inspector-body:visible').first
    preview = (405, 165, 470, 240)
    r.start()
    r.caption('', focus=(0, 0, VW, VH)); r.wait(700)
    card = body.locator('article').filter(has_text='NIGHT CITY').first
    r.caption('Pick your title in the Text tab', focus=(1045, 160, 555, 480)); r.move(1300, 330); r.wait(1400)
    r.caption('1. Click the timeline where the move starts', focus=(250, 520, 1100, 380))
    r.click_xy(at(0.25), ry, after=900)
    ed.scroll_to('Keyframes', 230); r.wait(500)
    add = body.get_by_role('button', name='Add keyframe at playhead for Layer 1')
    r.caption('2. Click “Add keyframe at playhead”', focus=(1045, 160, 555, 480))
    r.click(add, after=1300)
    r.caption('3. Move the playhead later', focus=(250, 520, 1100, 380))
    r.click_xy(at(3.6), ry, after=900)
    ed.scroll_to('X position', 40); r.wait(500)
    sliders = body.locator('input[type=range]')
    def slide(i, frm, to, ms=1300):
        bb = sliders.nth(i).bounding_box(); cx = lambda v: bb['x'] + 8 + (bb['width'] - 16) * v / 100
        r.drag(cx(frm), bb['y'] + bb['height']/2, cx(to), bb['y'] + bb['height']/2, ms=ms, after=500)
    r.caption('4. Move or resize the title', focus=(300, 150, 1300, 450))
    r.wait(500); r.mark('speed_start', x=3.0)
    slide(1, 22, 62); slide(0, 50, 30)
    fs = sliders.nth(2).bounding_box()
    r.drag(fs['x'] + 8 + (fs['width'] - 16) * 0.75, fs['y'] + fs['height']/2, fs['x'] + 8 + (fs['width'] - 16) * 0.48, fs['y'] + fs['height']/2, ms=1000, after=600)
    r.mark('speed_end')
    ed.scroll_to('Keyframes', 230); r.wait(300)
    r.caption('A second keyframe is added for you', focus=(1045, 160, 555, 480)); r.move(1350, 330); r.wait(1800)
    r.caption('5. Scrub the timeline to see it glide', focus=(250, 150, 1000, 750))
    r.drag(at(0.1), ry, at(4.0), ry, ms=2600, after=300)
    r.caption('6. Render the scene', focus=(250, 150, 1000, 450))
    r.click(pg.get_by_role('button', name='Render scene').first, after=500)
    r.click(pg.get_by_role('button', name='Continue').first, after=300)
    r.mark('skip_start')
    pg.locator('.render-status:visible', has_text='Scene ready').first.wait_for(timeout=240000); r.wait(800)
    r.mark('skip_end')
    r.click(pg.get_by_role('button', name='Rendered scene', exact=True).first, after=1200)
    pg.evaluate("()=>{const v=[...document.querySelectorAll('video')].find(v=>v.getBoundingClientRect().width>0); if(v){v.muted=true; v.currentTime=0; v.play();}}")
    r.caption('Your title now moves on its own', focus=preview, zoom=True)
    r.park(); r.move(5, 895, 400); r.wait(6000)
    r.stop()
print('done')
