import json

import pytest

from data_access.datafiles import THEMES_DIR
from interface_files import themes

REPO_THEMES = themes.Path(__file__).parent.parent / "data" / "themes"


def test_all_shipped_themes_are_valid_and_render_fully():
    shipped = sorted(p.stem for p in REPO_THEMES.glob("*.json"))
    loaded = themes.list_themes(REPO_THEMES)
    assert sorted(t.id for t in loaded) == shipped  # ninguno se descartó por errores
    assert themes.DEFAULT_THEME in shipped
    for theme in loaded:
        css = themes.stylesheet(theme.id, REPO_THEMES)
        assert "@" not in css, theme.id
        assert "QTreeWidget::item:selected" in css


def test_render_replaces_colors_and_alpha():
    colors = {"accent": "#00e5ff"}
    css = themes.render(
        "/* @nada */ a { color: @accent; border: 1px solid @accent/19; }", colors
    )
    assert (
        css.strip() == "a { color: #00e5ff; border: 1px solid rgba(0, 229, 255, 48); }"
    )


def test_render_unknown_color_fails_loudly():
    with pytest.raises(KeyError, match="@inexistente"):
        themes.render("a { color: @inexistente; }", {})


def _write(tmp_path, name, colors):
    (tmp_path / f"{name}.json").write_text(json.dumps({"name": name, "colors": colors}))


def _palette(**overrides):
    return {k: "#123456" for k in themes.COLOR_KEYS} | overrides


def test_eight_digit_colors_are_rejected(tmp_path):
    """Qt lee #RRGGBBAA como #AARRGGBB: la opacidad va en la plantilla."""
    _write(tmp_path, "malo", _palette(accent="#00e5ff30"))
    with pytest.raises(ValueError, match="#RRGGBB"):
        themes.load_theme(tmp_path / "malo.json")


def test_missing_colors_are_reported(tmp_path):
    colors = _palette()
    del colors["accent2"]
    _write(tmp_path, "incompleto", colors)
    with pytest.raises(ValueError, match="accent2"):
        themes.load_theme(tmp_path / "incompleto.json")


def test_broken_themes_are_skipped_and_unknown_falls_back(tmp_path):
    (tmp_path / "base.qss").write_text("a { color: @accent; }")
    _write(tmp_path, themes.DEFAULT_THEME, _palette(accent="#ff0000"))
    (tmp_path / "roto.json").write_text("{no es json")
    assert [t.id for t in themes.list_themes(tmp_path)] == [themes.DEFAULT_THEME]
    assert "#ff0000" in themes.stylesheet("no-existe", tmp_path)


def test_app_reads_themes_from_data_dir():
    assert THEMES_DIR.name == "themes"
