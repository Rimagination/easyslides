---
name: video
description: >
  Use for EasySlides 逐步演示、PowerPoint 制作过程录屏、视频倍速、原创配乐、
  连奏和水印（包括花字）. Also use to edit an existing EasySlides recording
  or create a standalone soundtrack for it.
---

# 视频制作

Read [PowerPoint Replay and Video Editing](../../workflows/powerpoint-replay.md)
and run its commands from the plugin runtime. Use the user's output location
or the workspace for generated files.

- For a new PPT, work with [easyslides](../easyslides/SKILL.md) during intake to
  settle the recording mode before authoring. Start live capture before the
  first insertion if the chosen authoring route supports it. For replay, use
  the exported PPTX after review.
- Use `powerpoint-demo --per-element` for an element-by-element PowerPoint
  replay. Add `--record` to capture it. Use `--delay` for the pause between
  elements and `replay-video edit --speed` for an existing video. A request
  for 录屏 alone means the PowerPoint window capture. Generate narration only
  for an explicit narration request.
- Share the silent raw MP4 first. Then ask about any unresolved choices for
  background music and 花字水印. Apply requested edits to a separate video.
- For an existing MP4, use `replay-video edit` for speed, music and credits.
  Use `legato` when the user asks for a smoother melody or fewer abrupt notes.
  Use the requested credit wording verbatim.
- For a standalone soundtrack, use `replay-video music` and match the
  requested format and duration.
