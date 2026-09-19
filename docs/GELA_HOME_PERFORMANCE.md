# Gela Home performance budget

Gela Home is a persistent desktop interface, so its idle cost matters more than a short-lived application screen.

## Target budgets

| State | Render target | Total CPU target | Working-set target |
| --- | ---: | ---: | ---: |
| Visible and idle | 24 FPS | 5% or less | 800 MB or less |
| Visible and active | 50 FPS | 10% or less | 850 MB or less |
| Covered by another application | 2 FPS | 1% or less | 800 MB or less |
| Minimized or hidden | Paused | 0.5% or less | 800 MB or less |

CPU percentages are normalized across all logical processors. Memory includes the native host, Node server, and every WebView2 child process.

## 2026-09-19 audit

Test PC: 16 logical processors and 15.2 GB physical RAM.

| Build | State | CPU | Working set | Notes |
| --- | --- | ---: | ---: | --- |
| Before adaptive rendering | Visible idle | 7.95% | 744.5 MB | Uncapped Three.js, SVG and shader animation |
| Adaptive rendering | Visible idle | 4.53% | 700.7 MB | 24 FPS idle cap; approximately 43% less CPU and 6% less working memory |

A controlled 60,000-particle avatar experiment measured 4.70% CPU and 708.7 MB. Because that was no improvement over the 80,000-particle result, the reduction was reverted to preserve visual fidelity. WebView compositing and bloom, rather than raw particle count, are the dominant visible-idle costs.

The always-on voice service was measured separately at about 0.67% CPU and 822 MB working set. Most of that memory is the loaded speech-recognition models.

## Runtime policy

- Foreground idle: 24 FPS.
- Foreground listening, thinking, or speaking: 50 FPS.
- Window loses focus: 2 FPS and CSS orbit animations pause.
- Document hidden or minimized: WebGL and SVG rendering pause.
- Focus/visibility restoration immediately restores the appropriate foreground rate.
- Three.js device pixel ratio is capped at 1.5 to avoid oversized high-DPI framebuffers.

## Repeatable measurement

Run `scripts/measure_home_performance.ps1` while installed Gela Home is open. Use `-Seconds 30` for a more stable sample. Run once with Home focused and once after focusing another application.

The dedicated Chrome DevTools performance connector was unavailable for this audit. Cold-load Core Web Vitals and a browser trace therefore remain a follow-up measurement, not a claimed result.
