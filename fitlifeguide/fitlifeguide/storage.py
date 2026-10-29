import asyncio
import os
from io import BytesIO
from uuid import uuid4

from django.conf import settings
from PIL import Image, ImageOps
from vercel.blob import delete_blob, put_blob

MAX_UPLOAD_BYTES = 4 * 1024 * 1024

if settings.BLOB_READ_WRITE_TOKEN:
    os.environ.setdefault('BLOB_READ_WRITE_TOKEN', settings.BLOB_READ_WRITE_TOKEN)


def upload_image(upload, folder):
    if not upload:
        return ''

    if getattr(upload, 'size', 0) > MAX_UPLOAD_BYTES:
        raise ValueError('Image must be 4 MB or smaller.')

    image = Image.open(upload)
    image = ImageOps.exif_transpose(image)
    image.thumbnail((1600, 1600))
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGB')

    output = BytesIO()
    image.save(output, format='WEBP', quality=82, method=6)
    body = output.getvalue()
    if len(body) > MAX_UPLOAD_BYTES:
        raise ValueError('Compressed image is still larger than 4 MB.')

    pathname = f'{folder}/{uuid4().hex}.webp'
    result = put_blob(
        pathname,
        body,
        access='public',
        content_type='image/webp',
        add_random_suffix=False,
    )
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    return result.url


def delete_image(url):
    if not url or not url.startswith('http'):
        return
    try:
        result = delete_blob(url)
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except Exception:
        pass
