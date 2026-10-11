import subprocess

import pytest

from conftest import make_video
from mptpro import captions, qa, thumbnail
from mptpro.captions import Word
from mptpro.config import CaptionsCfg
from mptpro.util import write_json

WORDS_AR = [Word(0.2, 0.7, "مرحبا"), Word(0.8, 1.2, "بكم"), Word(1.3, 1.9, "في"), Word(2.0, 2.6, "القناة."),
            Word(3.0, 3.5, "الجملة"), Word(3.6, 4.2, "الثانية")]


def frame(path, t, gray_size="270x480"):
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-s", gray_size, "-"], capture_output=True, check=True)
    return out.stdout


def test_chunking_breaks_on_sentence_end_gap_and_length():
    lines = captions.chunk_words(WORDS_AR, per_line=3)
    assert [len(x) for x in lines] == [3, 1, 2]  # 3 words, then "القناة." closes its line, then the rest
    gap = [Word(0, 1, "a"), Word(5, 6, "b")]
    assert len(captions.chunk_words(gap, per_line=4)) == 2


def test_ass_has_karaoke_timing_and_scaled_style():
    cfg = CaptionsCfg(font="Cairo", font_size_pct=5, margin_v_pct=10)
    ass = captions.build_ass(captions.chunk_words(WORDS_AR, 4), cfg, 1080, 1920)
    assert "PlayResX: 1080" in ass and "Style: Default,Cairo,96," in ass and ",192,1\n" in ass
    first = next(x for x in ass.splitlines() if x.startswith("Dialogue"))
    assert first.startswith("Dialogue: 0,0:00:00.20,0:00:02.60") and "{\\kf" in first and "مرحبا" in first
    plain = captions.build_ass([WORDS_AR[:2]], CaptionsCfg(karaoke=False), 1080, 1920)
    assert "{\\kf" not in plain


def test_arabic_captions_are_burned_into_the_frame(tmp_path):
    src = make_video(tmp_path / "in.mp4", seconds=5, color="0x203040")
    out = captions.caption_video(src, tmp_path / "out.mp4", CaptionsCfg(karaoke=False),
                                 transcriber=lambda *_: WORDS_AR)
    a, b = frame(src, 1.0), frame(out, 1.0)
    h = 480
    top, bottom = slice(0, 270 * h // 2), slice(270 * h // 2, None)
    assert a[top] == b[top], "top half must be untouched"
    assert a[bottom] != b[bottom], "captions must appear in the lower half"
    assert frame(src, 2.8) == frame(out, 2.8), "no caption between the two lines"


def test_no_speech_is_an_error(tmp_path):
    from mptpro.util import MptProError
    src = make_video(tmp_path / "in.mp4", seconds=2)
    with pytest.raises(MptProError, match="no speech"):
        captions.caption_video(src, tmp_path / "o.mp4", CaptionsCfg(), transcriber=lambda *_: [])


def test_thumbnail_is_1280x720(tmp_path):
    src = make_video(tmp_path / "in.mp4", seconds=4, size="640x360")
    out = thumbnail.make_thumbnail(src, "لماذا ينام الأخطبوط بعينين مفتوحتين؟", tmp_path / "t.jpg")
    size = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                           str(out)], capture_output=True, text=True).stdout.strip()
    assert size == "1280,720"


EP = {"id": "ep0002", "script": "Octopuses have three hearts. Two pump blood to the gills and one to the body. "
      "Their blood is blue because it uses copper.", "claims": ["three hearts"]}


def levels(report):
    return {r["check"]: r["level"] for r in report["results"]}


def test_qa_passes_a_normal_video(cfg, tmp_path):
    video = make_video(tmp_path / "v.mp4", seconds=25)
    report = qa.run_qa(EP, video, [{"id": "ep0001", "script": "Volcanoes erupt when pressure builds under rock."}], cfg)
    lv = levels(report)
    assert report["verdict"] == "pass", report
    assert lv["duration"] == lv["audio_stream"] == lv["aspect_ratio"] == lv["script_originality"] == "ok"
    assert lv["fact_check"] == "warn"


def test_qa_fails_broken_outputs(cfg, tmp_path):
    cases = {
        "duration": make_video(tmp_path / "short.mp4", seconds=5),
        "audio_stream": make_video(tmp_path / "mute.mp4", seconds=25, audio=False),
        "aspect_ratio": make_video(tmp_path / "wide.mp4", seconds=25, size="480x270"),
        "black_frames": make_video(tmp_path / "black.mp4", seconds=25, color="black"),
        "frozen_frames": make_video(tmp_path / "flat.mp4", seconds=25, color="0x336699"),
    }
    for check, video in cases.items():
        report = qa.run_qa({"id": "x", "script": "unique words only here"}, video, [], cfg)
        assert levels(report)[check] == "fail", (check, report)
        assert report["verdict"] == "fail"


def test_qa_flags_copied_scripts_and_repeated_hooks(cfg, tmp_path):
    video = make_video(tmp_path / "v.mp4", seconds=25)
    history = [{"id": f"ep{i:04d}", "script": "Did you know octopuses have three hearts and more"} for i in range(1, 5)]
    ep = {"id": "ep9", "script": "Did you know octopuses have three hearts and blue blood"}
    lv = levels(qa.run_qa(ep, video, history, cfg))
    assert lv["script_originality"] in ("warn", "fail") and lv["hook_variety"] == "warn"
    copy = qa.run_qa({"id": "ep9", "script": history[0]["script"]}, video, history, cfg)
    assert levels(copy)["script_originality"] == "fail" and copy["verdict"] == "fail"
