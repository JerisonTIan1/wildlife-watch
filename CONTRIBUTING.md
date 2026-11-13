# Working together

Clone `https://github.com/JerisonTIan1/wildlife-watch.git` after accepting your invitation. Follow the README setup.

1. Claim a task from `docs/BACKLOG.md` and agree on its owner.
2. Pull the latest main and create a focused branch, such as `feat/motor-control`, `feat/chassis`, or `feat/risk-estimator`.
3. Document how to run and verify each change, with measured evidence where relevant.
4. Ask a teammate to review before merging. This is a team convention, not an enforced branch rule.
5. Keep main runnable. Do not commit raw footage, model weights, secrets, virtual environments, or generated video.

## Responsibilities

- **JerisonTIan1:** wiring, power integration, H-bridge outputs, microcontroller state machine, USB receiver, command watchdog, motor tests.
- **Mechanical teammate (to be agreed):** chassis CAD/prints, mounts, assembly, alignment, and measured dimensions.
- **Perception teammate(s) (to be agreed):** camera capture, detection, position/range, uncertainty, path relevance, risk classification, USB sender.
- **Whole team:** shared interface, stop/re-arm behavior, integration and demo evidence.

Agree on [CONTROL_INTERFACE.md](docs/CONTROL_INTERFACE.md) before coding both endpoints. The laptop owns perception and risk; the controller owns motor outputs and local fault handling. Keep board/driver pin mapping separate from control logic.

For Python changes, run `python -m compileall -q wildlife_watch` and `python -m wildlife_watch.preview --help`. For firmware, record the exact board target, toolchain, compile result, and physical checks. A compile is not a motor test.

Clearly distinguish synthetic, recorded, proxy-target, and physical-hardware evidence. Keep model licenses and camera/driver documentation linked near the implementation.
