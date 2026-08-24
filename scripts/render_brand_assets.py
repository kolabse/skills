from __future__ import annotations

import argparse
import binascii
import math
import struct
import zlib
from pathlib import Path


SIZE = 512
SAMPLES = 2
BACKGROUND = (24, 33, 47, 255)
WHITE = (246, 248, 251, 255)
TEAL = (88, 196, 184, 255)
AMBER = (246, 184, 74, 255)
TRANSPARENT = (0, 0, 0, 0)


def inside_rounded_square(x: float, y: float, radius: float = 112) -> bool:
    nearest_x = min(max(x, radius), SIZE - radius)
    nearest_y = min(max(y, radius), SIZE - radius)
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius**2


def distance_to_segment(
    x: float, y: float, start: tuple[float, float], end: tuple[float, float]
) -> float:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length_squared = dx * dx + dy * dy
    position = ((x - x1) * dx + (y - y1) * dy) / length_squared
    position = min(1.0, max(0.0, position))
    nearest_x = x1 + position * dx
    nearest_y = y1 + position * dy
    return math.hypot(x - nearest_x, y - nearest_y)


def sample(x: float, y: float) -> tuple[int, int, int, int]:
    if not inside_rounded_square(x, y):
        return TRANSPARENT
    color = BACKGROUND
    if distance_to_segment(x, y, (142, 116), (142, 396)) <= 28:
        color = WHITE
    if (
        distance_to_segment(x, y, (354, 126), (214, 256)) <= 28
        or distance_to_segment(x, y, (214, 256), (354, 386)) <= 28
    ):
        color = TEAL
    if math.hypot(x - 214, y - 256) <= 34:
        color = AMBER
    return color


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def render(output: Path) -> None:
    rows = bytearray()
    sample_count = SAMPLES * SAMPLES
    for pixel_y in range(SIZE):
        rows.append(0)
        for pixel_x in range(SIZE):
            channels = [0, 0, 0, 0]
            for sample_y in range(SAMPLES):
                for sample_x in range(SAMPLES):
                    x = pixel_x + (sample_x + 0.5) / SAMPLES
                    y = pixel_y + (sample_y + 0.5) / SAMPLES
                    for index, value in enumerate(sample(x, y)):
                        channels[index] += value
            rows.extend(round(value / sample_count) for value in channels)

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", header)
    png += png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
    png += png_chunk(b"IEND", b"")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(png)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the deterministic kolabse Skills PNG from its vector geometry."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "assets"
        / "kolabse-skills-logo.png",
    )
    args = parser.parse_args()
    render(args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
