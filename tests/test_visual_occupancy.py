from PIL import Image, ImageDraw

from pipeline.visual_qc import frame_dark_structure, frame_near_black_ratio


def test_frame_near_black_ratio_distinguishes_empty_and_dense_frames(tmp_path):
    empty = tmp_path / "empty.png"
    dense = tmp_path / "dense.png"
    Image.new("RGB", (100, 100), "#090A0A").save(empty)
    Image.new("RGB", (100, 100), "#303232").save(dense)

    assert frame_near_black_ratio(empty, threshold=40) == 1.0
    assert frame_near_black_ratio(dense, threshold=40) == 0.0


def test_dark_structure_distinguishes_empty_canvas_from_readable_marks(tmp_path):
    empty = tmp_path / "empty.png"
    structured = tmp_path / "structured.png"
    Image.new("RGB", (160, 90), "#070808").save(empty)
    image = Image.new("RGB", (160, 90), "#070808")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 142, 72), outline="#F2F1ED", width=3)
    draw.text((28, 35), "SIGNED EVENT", fill="#F2F1ED")
    image.save(structured)
    assert frame_dark_structure(empty)["edge_ratio"] == 0.0
    assert frame_dark_structure(structured)["edge_ratio"] > 0.01
