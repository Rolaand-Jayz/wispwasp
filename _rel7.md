WispWasp can now turn a gallery picture into a short video clip, if you
want it to.

Download `WispWasp-0.1.7-setup.exe` below. New here? Read
`READ-ME-FIRST.md` first - it covers the Windows security warning and
how to try the app with nothing to download.

## Animate a picture

**Off by default.** Turn it on in Setup, where it says *Animate images
(video)*. That downloads 8.9 GB, so nothing happens unless you ask for
it - and if you leave it off, the option never appears anywhere.

Once on, right-click any gallery picture and choose **Animate this...**.
You pick a length and a shape, and the dialog says what you will get and
how long it takes:

| Length | Size | Time |
|---|---|---|
| 2.5 seconds | 1024 x 576 | about 3 min |
| 5 seconds | 768 x 432 | about 3 min |
| 7.5 seconds | 640 x 360 | about 3 min |
| 10 seconds | 512 x 288 | about 3 min |

Longer clips are made smaller so they fit in memory, which is why they
all take about the same time. A progress bar at the top of the gallery
counts down while it works, with a Stop button, and the rest of the app
keeps going.

**Worth knowing before you start:**

- **No sound.** Nothing that generates audio fits a 12 GB card.
- **No prompt.** This model takes the picture and nothing else.
- **Live generation waits.** ComfyUI does one job at a time, so anything
  the Live page hears while a clip is being made is queued and generated
  afterwards.
- Needs an NVIDIA card with 12 GB or more.

## Watching clips

Clips appear in the gallery beside your pictures, showing a still from
the first frame. **Filter by Video** in the Type dropdown to find them.
Click one to play it, with pause, a bar you can drag to scrub, and mute.

## Also in this release

The split layout's divider no longer jumps about once an image is on
screen, and has far more room to move.

## Known rough edges

- The installer is not code-signed, so Windows shows a warning. If your
  machine has Smart App Control switched on it may refuse to run it at
  all - see `READ-ME-FIRST.md`.
- Online images carry a small Pollinations watermark.

## Going back

Older releases stay on this page. Settings, images and models live
outside the program folder, so running an older installer over the top
loses nothing.
