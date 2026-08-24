from pathlib import Path


def test_caption_overlay_supports_full_phrase_static_mode() -> None:
    root = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"
    overlay = (root / "components" / "CaptionOverlay.tsx").read_text(
        encoding="utf-8"
    )
    talking_head = (root / "TalkingHead.tsx").read_text(encoding="utf-8")

    assert "animateWords?: boolean" in overlay
    assert "animateWords = true" in overlay
    assert ": color," in overlay
    assert "borderBottom: accentColor" in overlay
    assert "animateCaptionWords?: boolean" in talking_head
    assert "captionAccentColor?: string" in talking_head
    assert "animateWords={animateCaptionWords}" in talking_head
