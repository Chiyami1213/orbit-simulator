"""Generate packaging/icon.ico (navy tile, orange orbit, blue planet, yellow spacecraft)."""
import math
import pathlib
from PIL import Image, ImageDraw

S = 1024
im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=210, fill=(15, 22, 40, 255))
d.rounded_rectangle((18, 18, S - 19, S - 19), radius=195, outline=(44, 67, 128, 255), width=10)
cx, cy, a, b, rot = S * 0.5, S * 0.5, 360, 190, math.radians(-28)


def on_orbit(t):
    return (cx + a * math.cos(t) * math.cos(rot) - b * math.sin(t) * math.sin(rot),
            cy + a * math.cos(t) * math.sin(rot) + b * math.sin(t) * math.cos(rot))


d.line([on_orbit(i * 2 * math.pi / 240) for i in range(241)], fill=(255, 107, 74, 255), width=34, joint='curve')
fx, fy = cx - 120 * math.cos(rot), cy - 120 * math.sin(rot)          # focus (planet) on the major axis
r = 110
d.ellipse((fx - r, fy - r, fx + r, fy + r), fill=(76, 141, 246, 255))
d.ellipse((fx - r * .55, fy - r * .7, fx - r * .1, fy - r * .25), fill=(130, 180, 255, 255))
sx, sy = on_orbit(math.radians(35))
d.ellipse((sx - 42, sy - 42, sx + 42, sy + 42), fill=(245, 183, 59, 255))
im.save(pathlib.Path(__file__).with_name('icon.png'))                      # 1024 px source for the macOS .icns
out = pathlib.Path(__file__).with_name('icon.ico')
im.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('wrote', out)
