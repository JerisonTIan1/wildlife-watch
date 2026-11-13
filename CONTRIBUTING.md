# Working together

Clone `https://github.com/JerisonTIan1/wildlife-watch.git` after accepting your collaborator invitation. Follow the README setup.

1. Pick a task from `docs/BACKLOG.md` and agree on its owner in a GitHub issue.
2. Pull the latest `main`, then create a branch such as `feat/rgb-detector`, `feat/thermal-capture`, or `feat/alert-ui`.
3. Keep each pull request focused. Document how to run it and include real evidence of what works.
4. Ask a teammate to review before merging. This is a team convention, not an enforced branch rule.
5. Keep `main` runnable. Do not commit datasets, model weights, secrets, virtual environments, or generated video.

Suggested workstreams (assign together; these are not individual assignments):

| Workstream | Initial deliverable | Dependency |
| --- | --- | --- |
| Camera integration | Exact hardware inventory and repeatable capture | Physical cameras |
| Detection and evaluation | RGB baseline and labeled evaluation clips | Target species and usable footage |
| Interface and integration | Warning/fault UI consuming agreed detection events | Shared event fields below |

Proposed detection event fields: `source_id`, `frame_id`, `capture_time_ns`, `class_name`, `confidence`, `bbox_xyxy`, `model_id`. Coordinates are pixels in the original frame and confidence is a score, not a calibrated probability. Record timestamp origin and image dimensions. Finalize the contract in an issue before parallel implementation.

Run `python -m compileall -q wildlife_watch` and `python -m wildlife_watch.preview --help` before a PR. For capture changes, test a known video and the affected physical camera where available. Clearly distinguish synthetic, recorded, and live evidence.

Do not silently download weights at import time. Document model classes, licenses, runtime dependencies, and limitations. Obtain team agreement on a project license before a public release.
