import pytest

from mptpro import mptconfig
from mptpro.util import MptProError

EXAMPLE = '''listen_port = 8080
[app]
llm_provider = "moonshot"
# subtitle_provider = "commented"
subtitle_provider = "edge"
ollama_base_url = ""
ollama_model_name = ""
[whisper]
model_size = "large-v3"
device = "cpu"
compute_type = "int8"
[kokoro]
base_url = "http://127.0.0.1:8880/v1"
[chatterbox]
base_url = "http://127.0.0.1:4123/v1"
'''


def test_only_requested_keys_change_and_sections_are_respected():
    out = mptconfig.render(EXAMPLE, ollama_url="http://o:1/v1", ollama_model="m", kokoro_url="http://k:9/v1",
                           whisper_device="cuda", subtitle_provider="whisper", port=9000)
    assert 'llm_provider = "ollama"' in out and 'ollama_model_name = "m"' in out
    assert 'subtitle_provider = "whisper"' in out and "# subtitle_provider = \"commented\"" in out
    assert 'device = "cuda"' in out and 'compute_type = "float16"' in out and "listen_port = 9000" in out
    assert 'base_url = "http://k:9/v1"' in out and 'base_url = "http://127.0.0.1:4123/v1"' in out  # chatterbox untouched


def test_missing_key_is_an_error():
    with pytest.raises(MptProError, match="rename"):
        mptconfig.set_key("[app]\nx = 1\n", "app", "y", 2)
