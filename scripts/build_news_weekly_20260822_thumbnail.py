from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "news_weekly_20260822"
BRAND = OUT / "render_cache_earthy_v2" / "brand"
DEST = OUT / "thumbnail_ai_hit_pause.png"
W, H = 1280, 720


def face(size: int, bold: bool = False, display: bool = False):
    if display:
        name = "georgiab.ttf" if bold else "georgia.ttf"
    else:
        name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / name), size)


def paste_logo(canvas: Image.Image, name: str, center: tuple[int, int], size: int) -> None:
    path = BRAND / f"{name}.png"
    if not path.exists():
        return
    with Image.open(path).convert("RGBA") as logo:
        logo.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas.alpha_composite(logo, (center[0] - logo.width // 2, center[1] - logo.height // 2))


image = Image.new("RGBA", (W, H), "#E8EEE8")
draw = ImageDraw.Draw(image, "RGBA")
draw.ellipse((790, -260, 1500, 470), fill=(77, 139, 114, 255))
draw.ellipse((700, 410, 1210, 930), fill=(120, 157, 140, 135))
draw.text((58, 54), "THE WEEK IN AI", font=face(28, True), fill="#4D8B72")
draw.text((58, 132), "AI HIT", font=face(112, True, True), fill="#18251F")
draw.text((58, 246), "PAUSE", font=face(142, True, True), fill="#B8674F")
draw.text((62, 438), "THE STORY EVERYONE\nWILL BE TALKING ABOUT", font=face(34, True), fill="#50685D", spacing=10)

cx, cy = 1010, 380
shield = [(cx, cy - 225), (cx + 190, cy - 135), (cx + 155, cy + 120), (cx, cy + 235), (cx - 155, cy + 120), (cx - 190, cy - 135)]
draw.polygon(shield, fill=(242, 238, 229, 255), outline=(24, 37, 31, 255), width=7)
draw.line((cx, cy - 118, cx, cy + 105), fill="#18251F", width=17)
draw.line((cx - 105, cy - 7, cx + 105, cy - 7), fill="#18251F", width=17)
paste_logo(image, "openai", (cx, cy), 122)
draw.ellipse((1090, 485, 1240, 635), fill=(242, 238, 229, 255), outline=(24, 37, 31, 255), width=5)
paste_logo(image, "anthropic", (1165, 560), 86)
draw.rounded_rectangle((52, 630, 455, 686), radius=28, fill="#18251F")
draw.text((83, 643), "6 BIG STORIES · 10 MIN", font=face(24, True), fill="#F2EEE5")
image.convert("RGB").save(DEST, quality=96)
print(DEST)
