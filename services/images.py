"""Validate and re-encode images; never trust the filename or Content-Type."""
from io import BytesIO
from pathlib import Path
import warnings
from uuid import uuid4
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImage(ValueError):
    pass


class ImageTooLarge(InvalidImage):
    pass


def validate_image(upload, max_bytes=5 * 1024 * 1024, max_pixels=20_000_000):
    data = upload.stream.read(max_bytes + 1)
    upload.stream.seek(0)
    if len(data) > max_bytes:
        raise ImageTooLarge("写真は5MB以下にしてください。")
    extension = Path(upload.filename or "").suffix.lower()
    expected = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(extension)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                # MPO stores multiple JPEG images (including phone camera auxiliary images).
                # Decode only the primary image and re-encode it as an ordinary JPEG.
                accepted = {"JPEG", "MPO"} if expected == "JPEG" else {"PNG"}
                if not expected or image.format not in accepted:
                    raise InvalidImage("JPEGまたはPNGの正しい画像を選んでください。")
                if image.width * image.height > max_pixels:
                    raise InvalidImage("画像の縦横サイズが大きすぎます。")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                clean = ImageOps.exif_transpose(image).convert("RGB" if expected == "JPEG" else "RGBA")
                clean.info.clear()
                result = BytesIO()
                clean.save(result, format=expected)
                return result.getvalue(), ".jpg" if expected == "JPEG" else ".png"
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        if isinstance(error, InvalidImage):
            raise
        raise InvalidImage("画像を読み込めません。別の写真を選んでください。") from error


def save_image(upload, directory, **limits):
    data, suffix = validate_image(upload, **limits)
    key = uuid4().hex + suffix
    target = Path(directory) / key
    try:
        with target.open("xb") as stream:
            stream.write(data)
    except OSError:
        target.unlink(missing_ok=True)
        raise
    return key
