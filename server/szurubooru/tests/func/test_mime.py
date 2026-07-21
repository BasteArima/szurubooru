import pytest

from szurubooru.func import mime


@pytest.mark.parametrize(
    "input_path,expected_mime_type",
    [
        ("mp4.mp4", "video/mp4"),
        ("mov.mov", "video/quicktime"),
        ("webm.webm", "video/webm"),
        ("flash.swf", "application/x-shockwave-flash"),
        ("png.png", "image/png"),
        ("jpeg.jpg", "image/jpeg"),
        ("gif.gif", "image/gif"),
        ("webp.webp", "image/webp"),
        ("bmp.bmp", "image/bmp"),
        ("avif.avif", "image/avif"),
        ("avif-avis.avif", "image/avif"),
        ("heif.heif", "image/heif"),
        ("heic.heic", "image/heic"),
        ("heic-heix.heic", "image/heic"),
        ("text.txt", "application/octet-stream"),
    ],
)
def test_get_mime_type(read_asset, input_path, expected_mime_type):
    assert mime.get_mime_type(read_asset(input_path)) == expected_mime_type


def test_get_mime_type_for_empty_file():
    assert mime.get_mime_type(b"") == "application/octet-stream"


def _iso_bmff(brand):
    return b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 16


@pytest.mark.parametrize(
    "brand,expected_mime_type",
    [
        (b"isom", "video/mp4"),
        (b"iso2", "video/mp4"),
        (b"iso5", "video/mp4"),
        (b"iso6", "video/mp4"),
        (b"mp41", "video/mp4"),
        (b"mp42", "video/mp4"),
        (b"avc1", "video/mp4"),
        (b"dash", "video/mp4"),
        (b"M4V ", "video/mp4"),
        (b"M4VP", "video/mp4"),
        (b"qt  ", "video/quicktime"),
    ],
)
def test_get_mime_type_for_iso_bmff_brands(brand, expected_mime_type):
    assert mime.get_mime_type(_iso_bmff(brand)) == expected_mime_type


@pytest.mark.parametrize(
    "brand,expected_mime_type",
    [
        (b"avif", "image/avif"),
        (b"avis", "image/avif"),
        (b"mif1", "image/heif"),
        (b"heic", "image/heic"),
        (b"heix", "image/heic"),
    ],
)
def test_image_brands_win_over_generic_ftyp(brand, expected_mime_type):
    assert mime.get_mime_type(_iso_bmff(brand)) == expected_mime_type


def test_get_mime_type_for_audio_only_mpeg4():
    assert mime.get_mime_type(_iso_bmff(b"M4A ")) == "application/octet-stream"


@pytest.mark.parametrize(
    "mime_type,expected_extension",
    [
        ("video/mp4", "mp4"),
        ("video/webm", "webm"),
        ("video/quicktime", "mov"),
        ("application/x-shockwave-flash", "swf"),
        ("image/png", "png"),
        ("image/jpeg", "jpg"),
        ("image/gif", "gif"),
        ("image/webp", "webp"),
        ("image/bmp", "bmp"),
        ("image/avif", "avif"),
        ("image/heif", "heif"),
        ("image/heic", "heic"),
        ("application/octet-stream", "dat"),
    ],
)
def test_get_extension(mime_type, expected_extension):
    assert mime.get_extension(mime_type) == expected_extension


@pytest.mark.parametrize(
    "input_mime_type,expected_state",
    [
        ("application/x-shockwave-flash", True),
        ("APPLICATION/X-SHOCKWAVE-FLASH", True),
        ("application/x-shockwave", False),
    ],
)
def test_is_flash(input_mime_type, expected_state):
    assert mime.is_flash(input_mime_type) == expected_state


@pytest.mark.parametrize(
    "input_mime_type,expected_state",
    [
        ("video/webm", True),
        ("VIDEO/WEBM", True),
        ("video/mp4", True),
        ("VIDEO/MP4", True),
        ("video/quicktime", True),
        ("VIDEO/QUICKTIME", True),
        ("video/anything_else", False),
        ("application/ogg", True),
        ("not a video", False),
    ],
)
def test_is_video(input_mime_type, expected_state):
    assert mime.is_video(input_mime_type) == expected_state


@pytest.mark.parametrize(
    "input_mime_type,expected_state",
    [
        ("image/gif", True),
        ("image/png", True),
        ("image/jpeg", True),
        ("image/bmp", True),
        ("image/avif", True),
        ("image/heic", True),
        ("image/heif", True),
        ("IMAGE/GIF", True),
        ("IMAGE/PNG", True),
        ("IMAGE/JPEG", True),
        ("IMAGE/BMP", True),
        ("IMAGE/AVIF", True),
        ("IMAGE/HEIC", True),
        ("IMAGE/HEIF", True),
        ("image/anything_else", False),
        ("not an image", False),
    ],
)
def test_is_image(input_mime_type, expected_state):
    assert mime.is_image(input_mime_type) == expected_state


@pytest.mark.parametrize(
    "input_path,expected_state",
    [
        ("gif.gif", False),
        ("gif-animated.gif", True),
    ],
)
def test_is_animated_gif(read_asset, input_path, expected_state):
    assert mime.is_animated_gif(read_asset(input_path)) == expected_state


@pytest.mark.parametrize(
    "input_mime_type,expected_state",
    [
        ("image/gif", False),
        ("image/png", False),
        ("image/jpeg", False),
        ("image/avif", True),
        ("image/heic", True),
        ("image/heif", True),
        ("IMAGE/GIF", False),
        ("IMAGE/PNG", False),
        ("IMAGE/JPEG", False),
        ("IMAGE/AVIF", True),
        ("IMAGE/HEIC", True),
        ("IMAGE/HEIF", True),
        ("image/anything_else", False),
        ("not an image", False),
    ],
)
def test_is_heif(input_mime_type, expected_state):
    assert mime.is_heif(input_mime_type) == expected_state
