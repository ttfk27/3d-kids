# mptpro

A production layer on top of [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (MIT) for an
English YouTube channel on your own GPUs. It does not modify MoneyPrinterTurbo: it drives it through its HTTP API.

MoneyPrinterTurbo turns a script into a video. mptpro adds the parts around it:

| Stage | What it adds |
|---|---|
| `series` / `plan` | A series bible and an episode queue. Every new topic is checked against all earlier ones, so the channel does not drift into one template. |
| `draft` | Narration split into scenes, a visual prompt per scene, and a list of **factual claims** you must verify. |
| `produce` | Generates AI clips with **ComfyUI** (Wan / LTX / anything you can build a workflow for), spread over **all your GPUs** (one ComfyUI per GPU), resumable. Optional image-to-video with a reference image so the same character appears in every clip. MoneyPrinterTurbo then does voice, music and assembly. |
| captions | Optional word-timed captions with the spoken word highlighted (faster-whisper + libass). |
| `qa` | Automatic gate: duration, audio present, aspect ratio, black / frozen frames, silence, loudness, script overlap with earlier episodes, repeated hooks, repeated sentences. Then metadata (title, description, tags) with YouTube's limits enforced. |
| `review` / `approve` | A human approves every episode. Episodes with factual claims need `--facts-checked`. |
| `publish` | Scheduled upload through the official YouTube Data API v3 with the AI-content disclosure flag. Dry run unless you pass `--yes`. |

Why the gate and the approval step exist: YouTube's policy targets mass-produced, templated, low-effort channels
(the "inauthentic content" rule), and that is judged across the whole channel. Review the current wording on
YouTube's own help pages. Nothing here makes a channel profitable on its own; it makes quality repeatable.

## Setup

Needs `uv`, `ffmpeg`, [Ollama](https://ollama.com) (or any OpenAI-compatible LLM server), a
[Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) server for the voice, and ComfyUI for AI clips.

```bash
scripts/setup.sh                       # clones MoneyPrinterTurbo at a pinned commit, installs, writes its config.toml
(cd upstream/MoneyPrinterTurbo && uv run python main.py)    # terminal 1
COMFY_DIR=~/ComfyUI scripts/comfy_dual.sh                  # terminal 2: one ComfyUI per GPU (ports 8188, 8189)
source .venv/bin/activate
mptpro init                            # writes config.yaml: set channel, llm.model, voice
# workflows/README.md: export a Wan/LTX workflow from ComfyUI, then:
mptpro templatize workflows/raw_api.json workflows/video_api.json
mptpro doctor                          # checks ffmpeg, MoneyPrinterTurbo, LLM, every ComfyUI, workflow placeholders
```

No GPU yet? Set `mpt.video_source: pexels` (stock footage; needs a Pexels key in MoneyPrinterTurbo's config) and
skip ComfyUI.

## Daily use

```bash
mptpro run 3        # series (first time) -> plan -> draft -> produce -> qa for 3 episodes
mptpro review       # QA findings, the claims to verify, video paths
# watch the videos, fact-check the claims, edit workspace/episodes/<id>/episode.json if needed
mptpro approve ep0001 --facts-checked
mptpro publish      # dry run: shows the schedule
mptpro publish --yes
```

Each stage also runs alone: `plan N`, `draft`, `produce`, `qa`, `status`.

### YouTube upload notes (verify before relying on them)

- Create a Desktop OAuth client in Google Cloud, enable the YouTube Data API v3, save it as `client_secret.json`.
- As I understand YouTube's rules, uploads from an API project that has not passed Google's audit are forced to
  private, and each upload costs about 1,600 of the 10,000 default daily quota units. Check the current docs.
- `publish.synthetic_media: true` sets `status.containsSyntheticMedia`. Keep it on for AI-generated footage.
- `channel.made_for_kids` is `false` by default; set it truthfully.

## What is tested, and what is not

`pytest` runs 29 tests with real ffmpeg: ComfyUI client and two-GPU dispatch (fake ComfyUI server), workflow
templating, QA checks on synthetic broken videos, captions burned into video, scheduling, approval gate, config
writer. `MPT_DIR=/path/to/MoneyPrinterTurbo pytest tests/test_e2e_mpt.py` drives a **real MoneyPrinterTurbo** through a
whole episode (clips -> upload -> render -> download -> captions -> QA -> approve -> publish dry run).

**Not tested** (no GPU or accounts in the build environment): real ComfyUI with Wan/LTX, real Kokoro / Ollama /
faster-whisper, the actual YouTube upload. Expect small adjustments on first run, especially the ComfyUI workflow.
