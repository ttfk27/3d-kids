import pytest

from mptpro import similarity
from mptpro.config import load
from mptpro.util import MptProError, extract_json


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure!\n```json\n{"a": [1, 2]}\n```\nbye') == {"a": [1, 2]}
    assert extract_json('<think>hmm {"x":0}</think> here: [1,2]') == [1, 2]
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_config_rejects_unknown_keys(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("channel: {nmae: typo}\n")
    with pytest.raises(MptProError, match="nmae"):
        load(p)
    p.write_text("llm: {model: m}\ncaptions: {engine: libass}\n")
    cfg = load(p)
    assert cfg.llm.model == "m" and cfg.captions.engine == "libass" and cfg.root == tmp_path


def test_similarity_detects_rewrites_and_arabic_normalisation():
    a = "The octopus has three hearts and blue blood that carries oxygen using copper"
    assert similarity.jaccard(a, a) == 1.0
    assert similarity.jaccard(a, "Volcanoes form where tectonic plates collide and melt rock") < 0.1
    assert similarity.jaccard("أَحمد يحبُّ القراءة في المكتبة", "احمد يحب القراءه في المكتبه", n=2) == 1.0
    assert similarity.opening("Did you know that sharks", 3) == "did you know"
