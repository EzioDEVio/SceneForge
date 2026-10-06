# Timeline sizing, provider access and marker tutorial

Baseline: delivered source checkpoint `86a1469`. Prepared source changes only;
no new production frontend build, ZIP, Windows installer or GitHub publication.

The owner's two screenshots show an inaccessible draggable divider and lower
free-timeline tracks. The free timeline now has a visible **Drag to resize**
separator. Drag up/down, or focus it and use Arrow Up/Down (40 pixels), Home
(240 pixels), End (largest height that fits). Height is bounded to preserve the
application header, adjusts to the window, and is remembered per project in
this browser. Minimize hides the track area; Restore tracks returns it. Maximize
and Restore switch between the largest view and the chosen height. These view
controls do not change clip timing, source contents or Undo history.

AI Engines now opens a menu: **AI providers · API keys**, local image engines,
local voice engines, and help. Provider settings contain expandable forms for
the eight cloud providers already supported: OpenAI, ElevenLabs, Google Gemini,
Together AI, Cloudflare, Hugging Face, Google Veo and Runway. Each form uses the
existing provider API and credential store, with model/connection defaults from
the same catalog as the existing Settings drawer. The old Settings entry point,
account links and local-engine sections remain available. Blank keys cannot
save; keys clear after save or collapse; failed saves show the actual error.
Saving a profile does not trigger paid generation. Native Windows credential
storage and real account/model availability still require owner testing.

The companion **SceneForge-Markers-Step-by-Step.mp4** is a 100-second on-screen
guide made from actual app captures, with no voiceover. It demonstrates named
timeline markers, seeking/color/removal, Undo/Redo, range markers, manual AutoCut
preview/application, real beat detection using an uploaded synthetic rhythm and
beat AutoCut preview. It distinguishes marker spans from the free timeline's
Highlight range tool and map-route marker icons. The marker toolbar remains in
Scene assembly; this pass does not add a marker toolbar to Free timeline.

Validation: TypeScript, full frontend suites (334 editor checks plus remaining
suites and new provider interaction checks), real Chromium resize/free editing
and provider-access harness, and actual tutorial marker/AutoCut/beat workflows
passed. The test environment's DOM fixture needed a scrollIntoView shim; layout
scrolling itself was verified in Chromium. No real API keys or paid requests were
used. Windows testing is pending; this is source/browser validation.

Build approval remains required by HANDOFF_TO_CHATGPT.md section 1:
“Ask for the owner’s OK before creating another update build or checkpoint ZIP.”
The previous approval was used for the already-delivered Free-Timeline package.
