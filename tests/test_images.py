from io import BytesIO
from PIL import Image
from werkzeug.datastructures import FileStorage
import pytest
from services.images import InvalidImage, validate_image


def photo(format="PNG", name="photo.png"):
    stream = BytesIO()
    Image.new("RGB", (10, 10), "green").save(stream, format=format)
    stream.seek(0)
    return FileStorage(stream=stream, filename=name)


def test_valid_image():
    data, suffix = validate_image(photo())
    assert suffix == ".png"
    with Image.open(BytesIO(data)) as image:
        assert image.size == (10, 10)


@pytest.mark.parametrize("image", [lambda: FileStorage(stream=BytesIO(b"not an image"), filename="a.png"), lambda: photo("PNG", "a.jpg"), lambda: photo("GIF", "a.png")])
def test_invalid_image(image):
    with pytest.raises(InvalidImage):
        validate_image(image())


def test_capacity_and_pixels():
    with pytest.raises(InvalidImage):
        validate_image(photo(), max_bytes=8)
    with pytest.raises(InvalidImage):
        validate_image(photo(), max_pixels=50)


def test_mpo_primary_image_is_saved_as_plain_jpeg():
    stream = BytesIO()
    Image.new("RGB", (20, 30), "green").save(
        stream, format="MPO", save_all=True,
        append_images=[Image.new("RGB", (20, 30), "red")])
    stream.seek(0)
    with Image.open(BytesIO(stream.getvalue())) as original:
        assert original.format == "MPO"
        assert original.n_frames == 2
    data, suffix = validate_image(FileStorage(stream=stream, filename="camera.JPG"))
    assert suffix == ".jpg"
    with Image.open(BytesIO(data)) as saved:
        assert saved.format == "JPEG"
        assert saved.size == (20, 30)
        red, green, blue = saved.getpixel((0, 0))
        assert green > red and green > blue
