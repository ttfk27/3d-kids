import argparse
import shutil
import sys
from pathlib import Path

from . import comfy, mptconfig, pipeline, planner, scriptwriter, templatize
from .config import load
from .llm import LLM
from .mpt_client import MPTClient
from .util import MptProError, read_json, write_json
from .workspace import Workspace

HERE = Path(__file__).resolve().parent.parent


def _targets(ws: Workspace, ids: list[str], *statuses: str) -> list[str]:
    return ids or [e["id"] for e in ws.with_status(*statuses)]


def cmd_init(args, _cfg=None):
    dest = Path(args.config)
    if dest.exists():
        print(f"{dest} already exists")
    else:
        shutil.copyfile(HERE / "config.example.yaml", dest)
        print(f"wrote {dest}: edit channel/llm/mpt first")
    wf = dest.parent / "workflows"
    if not wf.exists() and (HERE / "workflows").exists():
        shutil.copytree(HERE / "workflows", wf)


def cmd_doctor(args, cfg):
    ok = True

    def line(good: bool, text: str, fatal: bool = True):
        nonlocal ok
        print(("  ok   " if good else "  FAIL " if fatal else "  warn ") + text)
        ok = ok and (good or not fatal)

    line(bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), "ffmpeg + ffprobe on PATH")
    line(MPTClient(cfg.mpt).ping(), f"MoneyPrinterTurbo reachable at {cfg.mpt.base_url}")
    try:
        LLM(cfg.llm).chat("Reply with the word ok.", "ping")
        line(True, f"LLM answers at {cfg.llm.base_url} ({cfg.llm.model})")
    except MptProError as e:
        line(False, str(e))
    if cfg.mpt.video_source == "local":
        for url in cfg.comfy.endpoints:
            line(comfy.ComfyClient(url).alive(), f"ComfyUI reachable at {url}")
        if not cfg.comfy.endpoints:
            line(False, "comfy.endpoints is empty (needed for video_source: local)")
        try:
            need = comfy.placeholders(comfy.load_workflow(cfg.path(cfg.comfy.workflow)))
            line("PROMPT" in need, f"workflow placeholders: {', '.join(sorted(need)) or 'none'}")
        except MptProError as e:
            line(False, str(e))
    if cfg.captions.engine == "libass":
        try:
            import faster_whisper  # noqa: F401
            line(True, "faster-whisper installed")
        except ImportError:
            line(False, "faster-whisper missing: pip install 'mptpro[captions]'")
    try:
        import googleapiclient  # noqa: F401
        line(True, "google client installed")
    except ImportError:
        line(False, "google client missing: pip install 'mptpro[youtube]' (only needed to publish)", fatal=False)
    sys.exit(0 if ok else 1)


def cmd_templatize(args, _cfg=None):
    src = read_json(Path(args.src))
    if not isinstance(src, dict):
        raise MptProError(f"cannot read workflow: {args.src}")
    wf, changes = templatize.templatize(src, with_image=args.image)
    write_json(Path(args.dst), wf)
    print("\n".join(changes) or "no changes made: add the placeholders by hand")


def cmd_mpt_config(args, _cfg=None):
    out = mptconfig.write(
        Path(args.mpt_dir), ollama_url=args.ollama_url, ollama_model=args.ollama_model, kokoro_url=args.kokoro_url,
        chatterbox_url=args.chatterbox_url, subtitle_provider=args.subtitle_provider,
        whisper_device=args.whisper_device, whisper_model=args.whisper_model, port=args.port)
    print(f"wrote {out}")


def cmd_series(args, cfg):
    ws = Workspace(cfg)
    if ws.series() and not args.force:
        print("series.json exists (use --force to regenerate)")
    else:
        ws.save_series(planner.make_series(LLM(cfg.llm), cfg))
    print(ws.series())


def cmd_plan(args, cfg):
    for ep in planner.plan_episodes(LLM(cfg.llm), cfg, Workspace(cfg), args.n):
        print(f"{ep['id']}  {ep['topic']}  -- {ep['angle']}")


def cmd_draft(args, cfg):
    ws, llm = Workspace(cfg), LLM(cfg.llm)
    for ep_id in _targets(ws, args.ids, "planned"):
        ep = scriptwriter.draft_episode(llm, cfg, ws, ep_id)
        print(f"{ep_id}  drafted: {ep['title']} ({len(ep['script'].split())} words)")


def cmd_produce(args, cfg):
    ws = Workspace(cfg)
    for ep_id in _targets(ws, args.ids, "drafted"):
        pipeline.produce(cfg, ws, ep_id)


def cmd_qa(args, cfg):
    ws, llm = Workspace(cfg), LLM(cfg.llm)
    for ep_id in _targets(ws, args.ids, "produced", "qa_failed"):
        report = pipeline.run_qa(cfg, ws, ep_id, llm)
        print(f"{ep_id}: {report['verdict']} ({report['warnings']} warning(s))")
        for r in report["results"]:
            if r["level"] != "ok":
                print(f"   {r['level']:<4} {r['check']}: {r['detail']}")


def cmd_review(args, cfg):
    ws = Workspace(cfg)
    for ep in ws.with_status("qa_passed", "qa_failed", "approved"):
        qa = read_json(ws.episode_dir(ep["id"]) / "qa.json", {})
        print(f"\n{ep['id']} [{ep['status']}] {ep.get('title')}\n  video: {ws.episode_dir(ep['id']) / ep.get('video', '')}")
        for r in qa.get("results", []):
            if r["level"] != "ok":
                print(f"  {r['level']:<4} {r['check']}: {r['detail']}")
        for c in ep.get("claims", []):
            print(f"  verify: {c}")


def cmd_approve(args, cfg):
    ws = Workspace(cfg)
    for ep_id in args.ids:
        pipeline.approve(ws, ep_id, args.facts_checked, args.force)
        print(f"{ep_id} approved")


def cmd_publish(args, cfg):
    done = pipeline.publish_approved(cfg, Workspace(cfg), args.limit, dry_run=not args.yes)
    if not args.yes:
        print("dry run only; add --yes to upload")
    elif not done:
        print("nothing approved to publish")


def cmd_run(args, cfg):
    ws, llm = Workspace(cfg), LLM(cfg.llm)
    if not ws.series():
        ws.save_series(planner.make_series(llm, cfg))
    missing = args.n - len(ws.with_status("planned", "drafted"))
    if missing > 0:
        planner.plan_episodes(llm, cfg, ws, missing)
    for ep in ws.with_status("planned")[: args.n]:
        scriptwriter.draft_episode(llm, cfg, ws, ep["id"])
    for ep in ws.with_status("drafted")[: args.n]:
        pipeline.produce(cfg, ws, ep["id"])
        report = pipeline.run_qa(cfg, ws, ep["id"], llm)
        print(f"{ep['id']}: qa {report['verdict']}")
    print("\nnext: `mptpro review`, then `mptpro approve <id>` and `mptpro publish`")


def cmd_status(args, cfg):
    counts: dict[str, int] = {}
    for e in Workspace(cfg).all():
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print(counts or "no episodes yet")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mptpro", description=__doc__)
    ap.add_argument("-c", "--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        p = sub.add_parser(name, **kw)
        p.set_defaults(fn=fn)
        return p

    add("init", cmd_init)
    add("doctor", cmd_doctor)
    p = add("templatize", cmd_templatize)
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--image", action="store_true", help="also make LoadImage nodes use {{IMAGE}}")
    p = add("mpt-config", cmd_mpt_config)
    p.add_argument("--mpt-dir", required=True)
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434/v1")
    p.add_argument("--ollama-model", default="qwen2.5:14b-instruct")
    p.add_argument("--kokoro-url", default="")
    p.add_argument("--chatterbox-url", default="")
    p.add_argument("--subtitle-provider", default="", help="'' (none), 'edge' or 'whisper'")
    p.add_argument("--whisper-device", default="cpu", choices=["cpu", "cuda"])
    p.add_argument("--whisper-model", default="large-v3")
    p.add_argument("--port", type=int, default=8080)
    add("series", cmd_series).add_argument("--force", action="store_true")
    add("plan", cmd_plan).add_argument("n", type=int, nargs="?", default=7)
    for name, fn in (("draft", cmd_draft), ("produce", cmd_produce), ("qa", cmd_qa)):
        add(name, fn).add_argument("ids", nargs="*")
    add("review", cmd_review)
    p = add("approve", cmd_approve)
    p.add_argument("ids", nargs="+")
    p.add_argument("--facts-checked", action="store_true", help="I verified the listed factual claims")
    p.add_argument("--force", action="store_true")
    p = add("publish", cmd_publish)
    p.add_argument("--yes", action="store_true", help="really upload (default is a dry run)")
    p.add_argument("--limit", type=int, default=0)
    add("run", cmd_run).add_argument("n", type=int, nargs="?", default=3)
    add("status", cmd_status)
    args = ap.parse_args(argv)
    try:
        if args.cmd in ("init", "templatize", "mpt-config"):
            return args.fn(args)
        args.fn(args, load(args.config))
    except MptProError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
