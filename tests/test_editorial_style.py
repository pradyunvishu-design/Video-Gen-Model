from PIL import Image, ImageDraw, ImageFont

from pipeline.editorial_style import (
    FORBIDDEN_EDITORIAL_HEX,
    draw_source_credit,
    is_forbidden_editorial_color,
    safe_editorial_accent,
)


def test_forbidden_editorial_accents_fall_back_to_neutral_slate() -> None:
    assert is_forbidden_editorial_color("#E8E32D")
    assert is_forbidden_editorial_color("#a855f7")
    assert safe_editorial_accent("#FFD21E") == "#83938C"
    assert safe_editorial_accent("#667C6D") == "#667C6D"


def test_source_credit_has_no_status_dot_or_forbidden_color() -> None:
    image = Image.new("RGBA", (620, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()
    box = draw_source_credit(
        draw, "Hugging Face", label_font=font, publisher_font=font, x=20, y=30,
    )

    colors = {"#%02X%02X%02X" % pixel[:3] for pixel in image.getdata() if pixel[3]}
    assert not (colors & FORBIDDEN_EDITORIAL_HEX)
    assert box[3] - box[1] == 48
    # A square newsroom lower-third keeps its outer corner; the rejected pill
    # treatment would make this pixel transparent.
    assert image.getpixel((box[0], box[1]))[3] > 0
