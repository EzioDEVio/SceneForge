# AutoCut — regular timeline markers

The owner placed two ordinary markers on image/video scenes and expected them in Beat source. The original Section D build offered only detected beat markers, music beds and timeline audio. This adjustment adds **Timeline markers (N)** for ordinary bookmarks created with **Marker** / **M**. It is selected by default when ordinary markers exist and detected beat markers do not.

Images and videos supply the pictures AutoCut changes. Music/audio supplies detected musical beats. Ordinary timeline markers provide manually chosen cuts and require no audio.

## Windows check

1. Select the scene you want to edit. It should contain at least two pictures, or a suitable video excerpt.
2. Put the playhead at a cut position inside that scene and click Marker (or press M). Repeat at another position inside the same scene.
3. Open Edit → AutoCut. Beat source should show **Timeline markers (2)**. Choose it.
4. Leave frequency at **Every marker**, then choose Preview AutoCut. Confirm the listed cut positions.
5. Apply, close and render the scene. Close Story tools before Undo/Redo.

The count includes your project's regular markers; only positions inside the selected scene create cuts. Scene start/end positions do not create extra internal cuts. The source is separate from **Existing timeline beat markers**, and both remain available alongside music/audio detection. Attached audio markers use the audio clip's current position.

## Verification

Production build and all existing frontend suites passed. The release093 and timeline-overlay Chromium regressions passed. The story-tools Chromium suite verifies that two regular markers are listed, are selected automatically without detected beat markers, preview cuts at 1.52 and 2.52 seconds, create exact 1520/1000/1480 ms clips, and Undo restores the prior five clips. It also verifies imported scenes open for editing and accept media. Previous Section D real FFmpeg/API results remain applicable; processing code is unchanged apart from clearer empty-marker error text.

Windows confirmation remains with the owner. Source versions and release state are unchanged. No push, tag or publication.
