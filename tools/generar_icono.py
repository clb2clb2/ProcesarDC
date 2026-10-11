from pathlib import Path
import struct

out_path = Path("c:/Proyectos-Github/ProcesarDC/assets/procesardc.ico")
out_path.parent.mkdir(parents=True, exist_ok=True)

width = 16
height = 16

bi_size = 40
pixel_bytes = width * height * 4
mask_row_bytes = ((width + 31) // 32) * 4
mask_bytes = mask_row_bytes * height
image_size = bi_size + pixel_bytes + mask_bytes

header = struct.pack("<HHH", 0, 1, 1)
entry = struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, image_size, 22)

bih = struct.pack(
    "<IIIHHIIIIII",
    bi_size,
    width,
    height * 2,
    1,
    32,
    0,
    pixel_bytes,
    0,
    0,
    0,
    0,
)

pixels = bytearray()
for y in range(height):
    for x in range(width):
        r = int(20 + (x / (width - 1)) * 60)
        g = int(80 + (y / (height - 1)) * 120)
        b = int(160 + ((x + y) / (2 * (width - 1))) * 70)
        a = 255
        pixels.extend([b, g, r, a])

rows = [pixels[i * width * 4 : (i + 1) * width * 4] for i in range(height)]
pixel_data = b"".join(reversed(rows))
and_mask = b"\x00" * mask_bytes

out_path.write_bytes(header + entry + bih + pixel_data + and_mask)
print(f"Icono generado: {out_path}")
