"""Clipboard privacy markers (Windows only). Restores the user's clipboard afterwards."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows clipboard")


@pytest.fixture
def clip():
    from voice_typer import clipboard

    saved = clipboard.get_text()
    yield clipboard
    if saved is not None:
        clipboard.set_text(saved)


def test_private_roundtrip(clip):
    assert clip.set_text("Bonjour Madame Gagnon, é à ç — test")
    assert clip.get_text() == "Bonjour Madame Gagnon, é à ç — test"
    assert clip.is_private()


def test_non_private(clip):
    assert clip.set_text("public", private=False)
    assert clip.get_text() == "public"
    assert not clip.is_private()
