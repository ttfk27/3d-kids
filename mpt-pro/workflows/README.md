# ComfyUI workflow for mptpro

mptpro does not ship a video workflow: node names change between ComfyUI versions and model builds, and a
workflow I could not run would be worse than none. You make one in two minutes:

1. In ComfyUI open **Workflow -> Browse Templates -> Video** and pick the Wan 2.2 (or LTX) template that runs on
   your 24 GB card. Generate one clip by hand to confirm it works.
2. **Workflow -> Export (API)** (not plain Save). Save it as `workflows/raw_api.json`.
3. `mptpro templatize workflows/raw_api.json workflows/video_api.json` and read the printed changes.
   Use `--image` for an image-to-video template if you want the same character in every clip.
4. `mptpro doctor` checks that `{{PROMPT}}` is present and every ComfyUI endpoint answers.

Placeholders mptpro fills: `{{PROMPT}}` `{{SEED}}` `{{WIDTH}}` `{{HEIGHT}}` `{{FRAMES}}` `{{FPS}}` `{{IMAGE}}`.
You can also type them into the JSON by hand. The workflow must end in a Save Video / Video Combine node.
