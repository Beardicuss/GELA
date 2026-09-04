from pathlib import Path
import sys

from PIL import Image


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from convert_frames import HEIGHT, WIDTH, fit_frame, rgb565_bytes  # noqa: E402


def test_fit_frame_has_exact_board_dimensions() -> None:
    image = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    assert fit_frame(image, (0, 0, 100, 100)).size == (WIDTH, HEIGHT)


def test_rgb565_is_little_endian() -> None:
    image = Image.new("RGB", (3, 1))
    image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    assert rgb565_bytes(image) == b"\x00\xf8\xe0\x07\x1f\x00"
