from pathlib import Path


def test_caption_separator_is_outside_inline_block_word_span():
    source = (
        Path(__file__).resolve().parents[2]
        / "remotion-composer"
        / "src"
        / "components"
        / "CaptionOverlay.tsx"
    ).read_text(encoding="utf-8")

    assert "{w.word}{i < page.words.length - 1 ? wordSeparator" not in source
    assert "{w.word}" in source
    assert '{i < page.words.length - 1 ? wordSeparator : ""}' in source
