from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_kraski_vertical_component_has_multimedia_and_caption_contract():
    source = (ROOT / "remotion-composer/src/KraskiVertical.tsx").read_text()

    assert "export type KraskiShot" in source
    assert "export type KraskiCaption" in source
    assert "OffthreadVideo" in source
    assert "<Img" in source
    assert "<Audio" in source
    assert "bright-observation" in source
    assert "parent-question" in source
    assert "small-discovery" in source
    assert "#FF6B00" in source


def test_root_registers_kraski_vertical_as_1080x1920():
    source = (ROOT / "remotion-composer/src/Root.tsx").read_text()

    assert 'id="KraskiVertical"' in source
    assert "component={KraskiVertical}" in source
    assert "width={1080}" in source
    assert "height={1920}" in source
    assert "calculateMetadata={calculateKraskiVerticalMetadata}" in source
