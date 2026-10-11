"""Turn a ComfyUI API-format export into a mptpro workflow by inserting {{PLACEHOLDERS}}.

Heuristics (always check the printed changes): the text feeding a sampler's `positive` input becomes
{{PROMPT}}; seed inputs become {{SEED}}; width/height/length become {{WIDTH}}/{{HEIGHT}}/{{FRAMES}};
LoadImage nodes become {{IMAGE}} when with_image is set.
"""
import copy

SEED_KEYS = {"seed", "noise_seed"}
SIZE_KEYS = {"width": "{{WIDTH}}", "height": "{{HEIGHT}}", "length": "{{FRAMES}}", "frames": "{{FRAMES}}",
             "num_frames": "{{FRAMES}}"}


def _is_link(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)


def templatize(workflow: dict, with_image: bool = False) -> tuple[dict, list[str]]:
    wf, changes = copy.deepcopy(workflow), []
    positive_ids = {str(n["inputs"]["positive"][0]) for n in wf.values()
                    if isinstance(n, dict) and _is_link(n.get("inputs", {}).get("positive"))}
    # Follow conditioning nodes (e.g. WanImageToVideo) back to the text encoder
    frontier = set(positive_ids)
    for _ in range(4):
        nxt = set()
        for nid in frontier:
            node = wf.get(nid, {})
            for key in ("positive", "conditioning"):
                link = node.get("inputs", {}).get(key)
                if _is_link(link):
                    nxt.add(str(link[0]))
        positive_ids |= nxt
        frontier = nxt
    for nid, node in wf.items():
        if not isinstance(node, dict) or "inputs" not in node:
            continue
        inputs = node["inputs"]
        if nid in positive_ids and isinstance(inputs.get("text"), str):
            inputs["text"] = "{{PROMPT}}"
            changes.append(f"node {nid} ({node.get('class_type')}): text -> {{{{PROMPT}}}}")
        for key in SEED_KEYS & inputs.keys():
            if not _is_link(inputs[key]):
                inputs[key] = "{{SEED}}"
                changes.append(f"node {nid} ({node.get('class_type')}): {key} -> {{{{SEED}}}}")
        for key, ph in SIZE_KEYS.items():
            if key in inputs and not _is_link(inputs[key]) and isinstance(inputs[key], int):
                inputs[key] = ph
                changes.append(f"node {nid} ({node.get('class_type')}): {key} -> {ph}")
        if with_image and node.get("class_type") == "LoadImage":
            inputs["image"] = "{{IMAGE}}"
            changes.append(f"node {nid} (LoadImage): image -> {{{{IMAGE}}}}")
    return wf, changes
