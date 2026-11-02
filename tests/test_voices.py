import os

from bookorbit_tts.engines.piper_engine import PiperEngine


def test_a_huggingface_layout_is_found_and_stray_files_are_not(tmp_path):
    root = tmp_path / "voices"
    voice = root / "en" / "en_US" / "ryan" / "high"
    voice.mkdir(parents=True)
    (voice / "en_US-ryan-high.onnx").write_bytes(b"model")
    (voice / "en_US-ryan-high.onnx.json").write_text(
        '{"language":{"code":"en_US","name_english":"English"}}',
        encoding="utf-8",
    )
    (root / "notes.onnx").write_bytes(b"nope")
    (root / "notes.onnx.json").write_text("{}", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    leaked = outside / "en_US-secret-high.onnx"
    leaked.write_bytes(b"secret")
    link = root / "en_US-secret-high.onnx"
    link.symlink_to(leaked)
    (root / "en_US-secret-high.onnx.json").write_text("{}", encoding="utf-8")

    found = PiperEngine(root).voices()
    assert [item.id for item in found] == ["en_US-ryan-high"]
    os.unlink(link)
