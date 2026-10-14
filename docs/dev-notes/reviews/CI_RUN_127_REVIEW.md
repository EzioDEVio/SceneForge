# CI run 127 — Script → Scenes browser polling correction

Run: https://github.com/EzioDEVio/SceneForge/actions/runs/37524728649
Source: f954a8cfdc60b8bd12758eef7eb21137d94aabe5

The validate job failed in `tests/browser/story_tools.cjs`, after adding two script scenes and invoking batch Undo/Redo. An exact scene-ID assertion observed four scenes while the second restore request was still completing. The separate installer workflow (Release run 55) completed successfully.

The installed Playwright polling implementation tests the predicate return value for truthiness before resolving it. An async predicate immediately returns a truthy Promise, so the old API waits could finish on the first false response instead of polling until the condition became true.

The story harness now polls API snapshots in Node, awaiting the data before checking the predicate and failing after a bounded ten seconds if the expected result never arrives. All seven remaining async API waits were corrected, covering AutoCut restoration, marker persistence, generated-scene media and stabilization Undo/Redo. Script scene Undo/Redo checks the complete ordered scene-ID set, preserves the three original scene IDs, and checks both imported narration texts.

For deterministic coverage, each imported-scene restore is delayed by 300 ms. Three Undo/Redo cycles run in each harness invocation, and exactly six restore requests must occur. This preserves the intermediate state that exposed the CI failure while requiring both restored scenes and their content to be present before success.

Validation: the final story harness passed three consecutive complete runs, totaling nine delayed batch Undo/Redo cycles. The full nine-harness browser command also passed. No paid provider calls were made. This correction changes tests/documentation only; application runtime source and the compiled frontend remain the same as the delivered corrected ZIP and the successful installer build.
