import json
from pathlib import Path
from types import SimpleNamespace

from tools.video.remotion_caption_burn import RemotionCaptionBurn


def test_remotion_props_use_static_file_relative_path(tmp_path, monkeypatch):
    remotion_root = tmp_path / "remotion-composer"
    (remotion_root / "public").mkdir(parents=True)

    input_path = tmp_path / "source.mp4"
    input_path.write_bytes(b"video")
    output_path = tmp_path / "rendered.mp4"

    tool = RemotionCaptionBurn()
    monkeypatch.setattr(tool, "_find_remotion_root", lambda: remotion_root)

    def fake_run(command, cwd=None):
        if command[0] == "ffprobe" and "format=duration" in command:
            return SimpleNamespace(stdout="10.0\n")
        if command[0] == "ffprobe" and "stream=width,height" in command:
            return SimpleNamespace(stdout="720x1280\n")
        output_arg = next(arg for arg in command if arg.startswith("--output="))
        Path(output_arg.split("=", 1)[1]).write_bytes(b"rendered")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(tool, "run_command", fake_run)

    result = tool._render_remotion(
        str(input_path),
        str(output_path),
        [{"word": "Тест", "startMs": 0, "endMs": 1000}],
        words_per_page=4,
        font_size=46,
        highlight_color="#FF6A00",
        animate_words=False,
    )

    assert result.success
    props_path = remotion_root / "public" / "demo-props" / "caption-burn-source.json"
    props = json.loads(props_path.read_text(encoding="utf-8"))
    assert props["videoSrc"] == "talking-head/source.mp4"
    assert not props["videoSrc"].startswith("public/")
    assert props["animateCaptionWords"] is False


def test_srt_blocks_force_caption_page_breaks(tmp_path):
    srt_path = tmp_path / "captions.srt"
    srt_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nПервая фраза\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nВторая фраза\n",
        encoding="utf-8",
    )

    captions = RemotionCaptionBurn()._srt_to_word_captions(str(srt_path))

    assert captions[1]["pageBreakAfter"] is True
    assert "pageBreakAfter" not in captions[0]
    assert captions[3]["pageBreakAfter"] is True
