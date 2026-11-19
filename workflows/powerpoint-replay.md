# PowerPoint Replay and Video Editing

Use this optional workflow for 制作过程录屏、倍速、原创配乐、连奏和文字水印.
Work from the current exported PPTX or the latest video the user intends to
revise. An existing recording can be edited directly.

## Ask Before Making a New PPT

On a host with PowerPoint capture, decide which mode the authoring route can
actually deliver. Before writing slides, use `clarify init --offer-recording`
and present the `recording` question from `clarify next` by itself. The
question is about recording the PowerPoint window while elements appear.

- **成稿回放** is the default mode offered. The popup says the finished deck
  will be replayed element by element in PowerPoint. Use `powerpoint-demo`
  on the final reviewed PPTX. Keep the replay associated with that deck
  revision. If the deck is revised after recording, identify the revision
  shown by the existing MP4 and use the updated reviewed export for a new
  recording requested by the user.
- **实时录制** requires an authoring route that adds objects to a visible
  PowerPoint window. Use `--recording-mode live` only after confirming that
  capability. Open the blank slide and capture the authoring window before
  inserting the first element. With `office.record_window.record_window`, use
  its pause function to capture the blank slide and to capture each insertion
  during the requested pause. If the user asked to see the first build but the route
  writes PPTX in the background, explain the limitation and ask whether they
  accept finished-deck replay before starting production.

Carry explicit choices in `--known-json` as `recording: "record"` (replay),
`"live"` (live capture) or `"skip"` (PPT only). State the chosen mode before
authoring even when the user already asked to record. Confirm a change of
mode with the user. If window capture is unavailable, explain that constraint.
The raw MP4 is silent. Generate a narrated video only on explicit request.

## Show or Record the Assembly

Run `powerpoint-demo` in a Windows desktop session with PowerPoint and
`pywin32`. It opens an independent copy and reveals the slide's native
objects in stacking order. The slide background and master form the starting
view. Use `--per-element` for 逐元素制作过程 to reveal group members separately
in the copy. A placed image, chart or native table still appears as one object.

```powershell
python scripts/easyslides.py powerpoint-demo deck.pptx --slide 3
python scripts/easyslides.py powerpoint-demo deck.pptx --per-element --delay 0.2 --record replay.mp4
```

Repeat `--slide` to request several pages. Omit it for the full deck. The
default delay is 3 seconds per step. A quick whole-deck demo can use 0.2
seconds per object. For a request to shorten each pause, set the recording or
replay interval with `--delay` (or the live author's pause). Use `--speed`
when the user asks to accelerate an existing video. State the pause used and
the finished duration. `--record` captures the PowerPoint window to a silent
MP4 and requires FFmpeg.

## Ask After the Recording Is Saved

Once the raw MP4 is saved and playable, share it and state whether it is live
capture or replay. Then use the host's native question tool for
**这段录屏要配背景音乐或加花字水印吗？** The choices are **保留原始录屏**、
**只配背景音乐**、**只加花字水印** and **背景音乐和花字水印都加**. Use the
same question in chat if there is no popup tool. If one choice is already
explicit, ask only about the other. A request for raw recording skips both.
Wait for the answer before applying optional edits.

Offer music presets or a supplied audio file when music is selected and the
user has yet to specify it. Keep watermark wording verbatim and ask for it if
missing. Use `flourish` when 花字 is chosen and `plain` for ordinary text.
Apply the chosen edits to the raw recording and save them in a separate MP4.

## Edit the Recording

Use `replay-video edit` with FFmpeg and FFprobe on PATH. Combine the requested
options in one command and write a new output. `--speed 2` doubles playback
speed. The editor keeps the source video frames and retimes existing audio at
the same pitch when no music replacement is selected.

```powershell
python scripts/easyslides.py replay-video edit replay.mp4 --out replay-edited.mp4 --speed 2 --music legato --watermark "视频由 @署名 使用Codex制作。" --watermark-style flourish
```

| User wants | Option |
|---|---|
| 壮阔、恢宏 | `--music epic` |
| 更多乐器和轮换的旋律 | `--music ensemble` |
| 音符衔接更顺、减少跳音 | `--music legato` |
| 指定音乐的节奏或音量 | `--bpm` for a preset, `--music-gain` in dB |
| 使用已有配乐 | `--music-file track.mp3` |
| 右下角文字水印 | `--watermark "原文"` |
| 描边花字水印 | `--watermark-style flourish`, optionally `--watermark-accent "昵称"` |

Music replaces the current audio stream and fits the finished video duration.
Keep the user's exact credit wording and punctuation. Flourish highlights an
`@mention` by default. Use `--watermark-font` if the default font lacks the
requested script. To replace a credit already burned into an MP4, start with
the corresponding uncredited recording and reapply the chosen speed and music.
Preview a frame of the finished video to check legibility and clearance from
page numbers. Report the finished file and its duration.

## Generate Music Only

```powershell
python scripts/easyslides.py replay-video music --duration 35.8 --style legato --out soundtrack.mp3
```

Original tracks are synthesized locally from an instrumental score, using
NumPy, SciPy and a General MIDI DLS bank. The default bank on Windows is
`gm.dls`. On other platforms supply `--soundbank` or use an existing music
file when editing a video. WAV export uses the synthesizer directly and MP3
export uses FFmpeg.
