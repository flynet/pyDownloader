"""File name sanitizing and name conflict tests (spec 11)."""

from __future__ import annotations

from pathlib import Path

from pydownloader.util.filenames import fits_path, sanitize_filename, unique_path


def test_forbidden_characters_are_replaced():
    name = sanitize_filename('Video: "Осень/Зима" #1 <>?*|')
    assert name.endswith(".mp4")
    for char in '<>:"/\\|?*':
        assert char not in name
    assert name.startswith("Video")


def test_cyrillic_and_spaces_are_kept():
    assert sanitize_filename("Обычный видеофильм 2024") == "Обычный видеофильм 2024.mp4"


def test_trailing_dots_and_spaces_are_dropped():
    assert sanitize_filename("Title..  ") == "Title.mp4"
    assert sanitize_filename("   ") == "video.mp4"
    assert sanitize_filename("") == "video.mp4"


def test_control_characters_are_replaced():
    assert sanitize_filename("Line\nNew\tTab") == "Line New Tab.mp4"


def test_windows_reserved_names_are_prefixed():
    assert sanitize_filename("CON") == "_CON.mp4"
    assert sanitize_filename("com3") == "_com3.mp4"


def test_long_title_is_cut_below_the_path_limit():
    title = "A" * 400
    name = sanitize_filename(title, max_length=120)
    assert len(name) <= 120
    assert name.endswith(".mp4")
    full = Path("C:\\Users\\Home\\Downloads") / name
    assert fits_path(full)


def test_unique_path_suffixes(tmp_path: Path):
    first = unique_path(tmp_path, "Видео")
    assert first.name == "Видео.mp4"
    first.write_bytes(b"")
    second = unique_path(tmp_path, "Видео")
    assert second.name == "Видео (1).mp4"
    second.write_bytes(b"")
    third = unique_path(tmp_path, "Видео")
    assert third.name == "Видео (2).mp4"


def test_fits_path_limit():
    assert fits_path(Path("C:\\apps\\out.mp4"))
    assert not fits_path(Path("C:\\" + "a" * 300))
