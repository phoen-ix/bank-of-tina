#!/usr/bin/env python3
"""
One-time script to generate PWA icons for Bank of Tina.
Run: python3 create_icons.py
Outputs: app/static/icons/icon-192.png  (192x192)
         app/static/icons/icon-512.png  (512x512)
No external dependencies — uses only stdlib (struct, zlib).
"""
import struct
import zlib
import os

# Design constants
BG_COLOR = (0x0d, 0x6e, 0xfd)   # Bootstrap blue #0d6efd
FG_COLOR = (0xff, 0xff, 0xff)   # White


def make_png(size: int) -> bytes:
    """Generate a square PNG of `size` pixels with a bank silhouette."""
    width = height = size
    # Create pixel buffer: list of rows, each row is a list of (R,G,B) tuples
    pixels = [[BG_COLOR] * width for _ in range(height)]

    # Bank silhouette: rectangles as fractions of icon size, centered with ~15% padding
    pad = size * 0.15
    draw_w = size - 2 * pad   # usable drawing width
    draw_h = size - 2 * pad   # usable drawing height

    def fill_rect(x0f, y0f, x1f, y1f):
        """Fill rectangle given as fractions of draw area (0.0–1.0), offset by padding."""
        x0 = int(pad + x0f * draw_w)
        y0 = int(pad + y0f * draw_h)
        x1 = int(pad + x1f * draw_w)
        y1 = int(pad + y1f * draw_h)
        for row in range(max(0, y0), min(height, y1)):
            for col in range(max(0, x0), min(width, x1)):
                pixels[row][col] = FG_COLOR

    # --- Bank building silhouette (all coordinates as fraction of draw area) ---
    # Roof/pediment: full width triangle approximated as a thick trapezoid
    fill_rect(0.10, 0.00, 0.90, 0.18)   # main pediment block
    fill_rect(0.20, 0.18, 0.80, 0.26)   # narrow ledge under pediment

    # Three columns (evenly spaced)
    col_w = 0.10
    col_top = 0.26
    col_bot = 0.78
    for cx in (0.20, 0.45, 0.70):        # left-edge of each column
        fill_rect(cx, col_top, cx + col_w, col_bot)

    # Base / steps
    fill_rect(0.10, 0.78, 0.90, 0.88)   # upper base
    fill_rect(0.05, 0.88, 0.95, 1.00)   # lower step

    # Build raw image data: filter byte 0x00 (None) prepended to each row
    raw_rows = []
    for row in pixels:
        row_bytes = b'\x00' + b''.join(bytes(p) for p in row)
        raw_rows.append(row_bytes)
    raw = b''.join(raw_rows)
    compressed = zlib.compress(raw, level=9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png = (
        b'\x89PNG\r\n\x1a\n'   # PNG signature
        + chunk(b'IHDR', ihdr_data)
        + chunk(b'IDAT', compressed)
        + chunk(b'IEND', b'')
    )
    return png


def main():
    out_dir = os.path.join('app', 'static', 'icons')
    os.makedirs(out_dir, exist_ok=True)
    for size in (192, 512):
        path = os.path.join(out_dir, f'icon-{size}.png')
        with open(path, 'wb') as f:
            f.write(make_png(size))
        print(f'Written {path}  ({size}x{size})')


if __name__ == '__main__':
    main()
