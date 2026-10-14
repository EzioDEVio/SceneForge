# SceneForge remote GPU relay — feasibility note

**Status:** proposal only. The current SceneForge build does not connect to Vast.ai or create rented instances.

## Why this can work

SceneForge already sends a normalized prompt, dimensions, duration and seed into a ComfyUI API workflow. A remote ComfyUI worker can execute that same workflow on a rented NVIDIA GPU and return a video asset. Text-to-video is the lowest-risk first experiment because it sends only the prompt; image-to-video would upload user media and needs a stronger consent and privacy flow.

Vast.ai exposes rented GPU instances through its marketplace and CLI/API. Offers come from individual hosts and data centers with different reliability, locations, bandwidth, storage and prices. Compute is charged while running, but storage continues to accrue while an instance is stopped; bandwidth can add cost, and an instance must be deleted to stop storage charges. Therefore a low advertised GPU hourly rate is not the same as a low all-in cost per clip.

## Recommended prototype

Use one temporary, user-controlled Vast account and benchmark the existing ComfyUI Wan 2.2 TI2V 5B workflow. Test one prompt at 480p, then 720p if memory/performance allow. Measure one, two and three candidates, because SceneForge generates candidates sequentially.

Record these values for each run:

| Measure | What to include |
|---|---|
| Startup | Instance provisioning, ComfyUI start and model download/cache time |
| Compute | GPU rental time from instance start through completed generation and file export |
| Storage | Disk charge from create through destroy, including model files |
| Transfer | Prompt/workflow input, generated video download, and any bandwidth fee |
| Reliability | Instance availability, interrupted jobs, retry behavior and cleanup success |
| Quality | Dimensions, duration, motion quality, audio, decode, captions, render and export |

Calculate the effective cost as **compute + storage + transfer + any failed-run cost**, then compare that with the equivalent per-second Google/Runway estimate already shown in SceneForge. Include warm-cache and first-run results separately: the first run may spend substantial time and bandwidth downloading multi-gigabyte weights.

## Product integration shape

If the benchmark is compelling, build this as an optional remote-GPU connector or a separate companion project before adding it to the default provider list:

1. User chooses a supported GPU offer and sees a cost ceiling covering compute, disk and transfer.
2. User confirms that the prompt (and any reference media, if enabled) leaves their computer and is sent to the selected host.
3. A job-scoped credential starts one temporary worker. The app never stores Vast credentials in a workflow file or generated asset.
4. The worker runs a fixed, reviewed ComfyUI image and workflow. It accepts only the job payload, reports progress and streams the result back through an authenticated channel.
5. SceneForge validates the video as it does local/cloud output, then requests instance destruction on success, cancellation and failure. The UI reports cleanup failures and keeps a retry/cleanup action visible.
6. The app reconciles actual compute, disk and bandwidth charges against the estimate; it does not silently retry a request that may already have incurred cost.

The first version should be text-to-video only, use short 480p clips, and not upload project media. Image-to-video should wait until privacy, upload size, retention and host selection are explicit and tested.

## Open questions before integration

- Which Vast instance contract and offer types give a reliable hard spend ceiling?
- How will credentials be stored and revoked, and who controls the Vast account and payment method?
- How should the app handle interrupted/spot instances, uncertain provider job status, duplicate billing, or failed deletion?
- Can the user's media be routed securely without opening the local ComfyUI port to the public internet?
- Does a warm model cache save enough time/money to justify continuing storage charges?
- Does the current Wan license and each user's intended use permit their planned outputs?

## References

- [Vast.ai marketplace concepts and host variability](https://docs.vast.ai/guides/concepts)
- [Vast.ai instance pricing, storage and bandwidth](https://docs.vast.ai/guides/instances/pricing)
- [Vast.ai storage behavior](https://docs.vast.ai/guides/instances/storage/types)
- [Vast.ai CLI instance cleanup](https://docs.vast.ai/cli/hello-world)
- [ComfyUI Wan 2.2 5B workflow and offloading](https://docs.comfy.org/tutorials/video/wan/wan2_2)
