"""Generate the installer's wizard artwork (branded navy-to-blue side panel + small header image) in several DPI sizes -> packaging/wizard/*.bmp

Inno Setup shows the large image on the welcome and finish pages and the small image on the inner pages. Several sizes are listed in
installer.iss so the wizard stays sharp at 100-250 % display scaling.
"""
import math
import pathlib
from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path(__file__).with_name('wizard'); OUT.mkdir(exist_ok=True)
SS = 3                                                              # supersampling for smooth edges


def font(size, bold=False):
    for name in (('segoeuib.ttf' if bold else 'segoeui.ttf'), ('arialbd.ttf' if bold else 'arial.ttf'), 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def logo(d, x, y, s):
    """The app icon (navy tile, orange orbit, blue planet, yellow spacecraft) drawn at (x, y) with side s."""
    d.rounded_rectangle((x, y, x + s, y + s), radius=s * 0.22, fill=(15, 22, 40), outline=(44, 67, 128), width=max(1, int(s * 0.02)))
    cx, cy, a, b, rot = x + s / 2, y + s / 2, s * 0.355, s * 0.185, math.radians(-28)
    pt = lambda t: (cx + a * math.cos(t) * math.cos(rot) - b * math.sin(t) * math.sin(rot), cy + a * math.cos(t) * math.sin(rot) + b * math.sin(t) * math.cos(rot))
    d.line([pt(i * 2 * math.pi / 200) for i in range(201)], fill=(255, 107, 74), width=max(2, int(s * 0.033)), joint='curve')
    fx, fy, r = cx - s * 0.117 * math.cos(rot), cy - s * 0.117 * math.sin(rot), s * 0.107
    d.ellipse((fx - r, fy - r, fx + r, fy + r), fill=(76, 141, 246)); sx, sy = pt(math.radians(35)); q = s * 0.04
    d.ellipse((sx - q, sy - q, sx + q, sy + q), fill=(245, 183, 59))


def side(w, h):
    W, H = w * SS, h * SS; im = Image.new('RGB', (W, H)); d = ImageDraw.Draw(im)
    top, bot = (10, 26, 62), (31, 99, 214)
    for y in range(H):                                              # vertical gradient, like the reference panel
        t = y / (H - 1); d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    for k, alpha in enumerate((30, 24, 18, 12)):                    # faint concentric orbits, lower half
        rx, ry = W * (0.55 + 0.35 * k), H * (0.16 + 0.11 * k); od.ellipse((W * 0.5 - rx, H * 0.78 - ry, W * 0.5 + rx, H * 0.78 + ry), outline=(255, 255, 255, alpha), width=max(2, W // 90))
    od.ellipse((W * 0.62, H * 0.66, W * 0.62 + W * 0.2, H * 0.66 + W * 0.2), fill=(255, 255, 255, 26))
    im = Image.alpha_composite(im.convert('RGBA'), ov); d = ImageDraw.Draw(im)
    s = int(W * 0.46); logo(d, (W - s) // 2, int(H * 0.09), s)
    d.text((W / 2, H * 0.36), 'Orbit', font=font(int(W * 0.17), True), fill=(255, 255, 255), anchor='mm')
    d.text((W / 2, H * 0.36 + W * 0.17), 'Simulator', font=font(int(W * 0.17), True), fill=(255, 255, 255), anchor='mm')
    d.text((W / 2, H * 0.36 + W * 0.36), 'orbit mechanics, visualised', font=font(int(W * 0.075)), fill=(190, 212, 255), anchor='mm')
    return im.convert('RGB').resize((w, h), Image.LANCZOS)


def small(w, h):
    W, H = w * SS, h * SS; im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im); s = int(min(W, H) * 0.86)
    logo(d, (W - s) // 2, (H - s) // 2, s); return im.resize((w, h), Image.LANCZOS)


for w, h in ((164, 314), (246, 459), (328, 604), (410, 797)):
    side(w, h).save(OUT / f'side-{w}.bmp')
for w, h in ((55, 55), (83, 80), (110, 106), (138, 140)):
    small(w, h).save(OUT / f'small-{w}.bmp')
print('wrote', len(list(OUT.glob('*.bmp'))), 'images to', OUT)
