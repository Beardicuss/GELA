"""Convert Gela face artwork into mPython Board 3.0 RGB565 frames."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from PIL import Image


WIDTH = 320
HEIGHT = 172
BACKGROUND = (0, 0, 0)
ASSET_MAP = {
    "idle/idle_middle.webp": "idle_0.bin",
    "idle/idle_left.webp": "idle_1.bin",
    "idle/idle_right.webp": "idle_2.bin",
    "idle/idle_downward.webp": "idle_3.bin",
    "idle/idle_middle_eyeclose.webp": "idle_blink.bin",
    "listening/listening.webp": "listen.bin",
    "listening/listening_blink.webp": "listen_blink.bin",
    "thinking/thinking.webp": "think.bin",
    "thinking/thinking_blink.webp": "think_blink.bin",
    "error/error.webp": "error.bin",
    "error/error_blink.webp": "error_blink.bin",
    "success/success.webp": "success.bin",
    "success/success_blink.webp": "success_blink.bin",
    "talking/mouth_open.webp": "talk_open.bin",
    "talking/mouth_closed.webp": "talk_closed.bin",
}


def content_box(images: list[Image.Image], alpha_threshold: int = 32) -> tuple[int, int, int, int]:
    boxes = []
    for image in images:
        alpha = image.getchannel("A").point(lambda value: 255 if value > alpha_threshold else 0)
        box = alpha.getbbox()
        if box:
            boxes.append(box)
    if not boxes:
        return (0, 0, images[0].width, images[0].height)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def fit_frame(image: Image.Image, crop: tuple[int, int, int, int]) -> Image.Image:
    cropped = image.crop(crop)
    cropped.thumbnail((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (*BACKGROUND, 255))
    x = (WIDTH - cropped.width) // 2
    y = (HEIGHT - cropped.height) // 2
    canvas.alpha_composite(cropped, (x, y))
    return canvas.convert("RGB")


def rgb565_bytes(image: Image.Image) -> bytes:
    output = bytearray(image.width * image.height * 2)
    offset = 0
    pixels = (
        image.get_flattened_data()
        if hasattr(image, "get_flattened_data")
        else image.getdata()
    )
    for red, green, blue in pixels:
        value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        struct.pack_into("<H", output, offset, value)
        offset += 2
    return bytes(output)


def save_board_png(image: Image.Image, destination: Path, colors: int = 256) -> None:
    """Write a compact RGB PNG compatible with the board's LVGL decoder."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    board_frame = image.quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG,
    ).convert("RGB")
    board_frame.save(destination, optimize=True)


def convert_single(source: Path, destination: Path, colors: int = 256) -> None:
    """Convert one reference-aligned transparent artwork into a board frame."""
    with Image.open(source) as original:
        # Gela's source artwork shares this 1024px reference composition.
        frame = fit_frame(original.convert("RGBA"), (20, 70, 1001, 914))
    save_board_png(frame, destination, colors)


def convert(source: Path, output: Path) -> dict[str, object]:
    missing = [name for name in ASSET_MAP if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing assets: " + ", ".join(missing))

    originals = [Image.open(source / name).convert("RGBA") for name in ASSET_MAP]
    crop = content_box(originals)
    output.mkdir(parents=True, exist_ok=True)
    preview = output.parent / "preview"
    preview.mkdir(parents=True, exist_ok=True)
    board_frames = output.parent / "board_frames"
    board_frames.mkdir(parents=True, exist_ok=True)

    files = []
    for (source_name, output_name), original in zip(ASSET_MAP.items(), originals):
        frame = fit_frame(original, crop)
        payload = rgb565_bytes(frame)
        if len(payload) != WIDTH * HEIGHT * 2:
            raise RuntimeError(f"Unexpected frame size for {output_name}")
        (output / output_name).write_bytes(payload)
        png_name = output_name.replace(".bin", ".png")
        frame.save(preview / png_name, optimize=True)
        # This firmware's LVGL PNG decoder crashes on indexed PNGs. Quantize
        # the palette for compression, then store it as ordinary RGB.
        save_board_png(frame, board_frames / png_name)
        files.append(
            {
                "source": source_name,
                "file": output_name,
                "bytes": len(payload),
                "board_png": png_name,
                "board_png_bytes": (board_frames / png_name).stat().st_size,
            }
        )

    manifest = {
        "format": "RGB565_LE",
        "width": WIDTH,
        "height": HEIGHT,
        "background": "#000000",
        "shared_crop": list(crop),
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--single", action="store_true")
    parser.add_argument("--colors", type=int, choices=(32, 64, 128, 256), default=256)
    args = parser.parse_args()
    if args.single:
        convert_single(args.source, args.output, args.colors)
        print(f"Converted {args.source} to {args.output}")
        return
    manifest = convert(args.source, args.output)
    print(f"Converted {len(manifest['files'])} frames to {args.output}")


if __name__ == "__main__":
    main()
