# Inspector review adjustments — awaiting owner build approval

The owner requires explicit OK before creating any further update build or checkpoint ZIP.

- Clip speed has cards for playback speed, speed ramp, slow motion and freeze frame, with short help and theme-aware selected options. All existing options remain.
- Timeline image/text Apply feedback shows Saving…, Saved, Apply changes after another edit, and Retry changes on failure. Failed edits remain in the draft. Duplicate submissions share one pending save.
- Added component coverage for delayed saving, saved/edit transitions, failed save/retry and speed controls; browser regression assertions cover the Saved/edit transition.

Validation: TypeScript no-emit check and focused inspector checks passed. All six existing frontend suites passed. The added focused inspector suite passed separately. Browser assertions are added but have not been run against a packaged build; Windows and packaged-build validation remain pending. No production build, checkpoint ZIP, push, tag or publication has been performed for these adjustments.
