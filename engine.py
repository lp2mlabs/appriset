"""Offline, non-destructive image conversion. No network access."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

from PIL import Image, ImageCms, ImageOps, features

SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp', '.avif', '.bmp', '.tif', '.tiff'}
SOURCE_FORMATS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP',
                  '.avif': 'AVIF', '.bmp': 'BMP', '.tif': 'TIFF', '.tiff': 'TIFF'}
Image.MAX_IMAGE_PIXELS = 80_000_000


class Cancelled(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    format: str = 'AUTO'
    quality: int = 80
    width: int = 1920
    height: int = 1080
    mode: str = 'fit'
    upscale: bool = False
    target_kb: int = 0

    def validate(self):
        if self.format not in {'AUTO', 'WEBP', 'AVIF', 'ORIGINAL'}:
            raise ValueError('Format tidak dikenal.')
        if not 25 <= self.quality <= 100:
            raise ValueError('Kualitas harus 25–100.')
        if not (0 <= self.width <= 12000 and 0 <= self.height <= 12000):
            raise ValueError('Dimensi harus 1–12000 piksel, atau 0 untuk ukuran asli.')
        if bool(self.width) != bool(self.height):
            raise ValueError('Lebar dan tinggi harus diisi bersama.')
        if self.mode not in {'fit', 'crop'} or not 0 <= self.target_kb <= 100000:
            raise ValueError('Pengaturan tidak valid.')


@dataclass
class Result:
    source: str
    output: str
    original_bytes: int
    output_bytes: int
    original_width: int
    original_height: int
    width: int
    height: int
    format: str
    quality: int
    target_met: bool

    @property
    def savings(self):
        return 100 * (1 - self.output_bytes / self.original_bytes)

    def to_dict(self):
        return {**asdict(self), 'savings_percent': round(self.savings, 2)}


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        if opened.width * opened.height > Image.MAX_IMAGE_PIXELS:
            raise ValueError('Gambar melebihi batas 80 megapiksel. Perkecil sumber terlebih dahulu.')
        if getattr(opened, 'n_frames', 1) > 1:
            raise ValueError('Gambar animasi/multihalaman belum didukung; gunakan gambar statis.')
        opened.load()
        image = ImageOps.exif_transpose(opened)
        alpha = image.convert('RGBA').getchannel('A') if 'A' in image.getbands() or 'transparency' in image.info else None
        icc = image.info.get('icc_profile')
        if icc:
            try:
                image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                                  ImageCms.createProfile('sRGB'), outputMode='RGB')
            except (ImageCms.PyCMSError, OSError, ValueError) as exc:
                raise ValueError('Profil warna tidak dapat dibaca. Ekspor sumber sebagai sRGB terlebih dahulu.') from exc
        else:
            image = image.convert('RGB')
        if alpha is not None:
            image.putalpha(alpha)
        image.info.clear()  # GPS/EXIF and other identifying metadata are not copied.
        return image


def resize_image(image: Image.Image, settings: Settings) -> Image.Image:
    settings.validate()
    if not settings.width:
        return image.copy()
    width, height = settings.width, settings.height
    if settings.mode == 'fit':
        ratio = min(width / image.width, height / image.height)
        if not settings.upscale:
            ratio = min(ratio, 1)
        size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
        return image.resize(size, Image.Resampling.LANCZOS) if size != image.size else image.copy()
    # If enlarging is disabled, shrink the requested box proportionally.
    if not settings.upscale:
        scale = min(1, image.width / width, image.height / height)
        width, height = max(1, int(width * scale)), max(1, int(height * scale))
    return ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def encode(image: Image.Image, fmt: str, quality: int) -> bytes:
    buffer = io.BytesIO()
    options = {'quality': quality}
    if fmt == 'AVIF':
        options.update(speed=6, max_threads=min(4, os.cpu_count() or 1), subsampling='4:4:4')
    elif fmt == 'WEBP':
        options.update(method=6)
        if quality == 100:
            options['lossless'] = True
    elif fmt == 'JPEG':
        image = image.convert('RGB')
        options.update(optimize=True, progressive=True, subsampling=0)
    elif fmt == 'PNG':
        options = {'optimize': True, 'compress_level': 9}
    elif fmt == 'TIFF':
        options = {'compression': 'tiff_adobe_deflate'}
    elif fmt == 'BMP':
        options = {}
    image.save(buffer, format=fmt, **options)
    return buffer.getvalue()


def compress(source: Path, folder: Path, settings: Settings,
             cancelled: Callable[[], bool] = lambda: False,
             stage: Callable[[str], None] = lambda _: None) -> Result:
    settings.validate()
    source, folder = Path(source).resolve(), Path(folder).resolve()
    if source.suffix.lower() not in SUPPORTED:
        raise ValueError('Format sumber belum didukung.')
    if cancelled():
        raise Cancelled()
    image = load_image(source)
    original_size = image.size
    image = resize_image(image, settings)
    codecs = (['AVIF', 'WEBP'] if settings.format == 'AUTO' else
              [SOURCE_FORMATS[source.suffix.lower()]] if settings.format == 'ORIGINAL' else [settings.format])
    candidates = []
    errors = []
    for fmt in codecs:
        if fmt in {'AVIF', 'WEBP'} and not features.check('avif' if fmt == 'AVIF' else 'webp'):
            errors.append(f'Encoder {fmt} tidak tersedia.')
            continue
        if cancelled():
            raise Cancelled()
        stage(f'Mengompres {fmt}…')
        try:
            data = encode(image, fmt, settings.quality)
            quality = settings.quality if fmt in {'AVIF', 'WEBP', 'JPEG'} else 100
            if fmt in {'AVIF', 'WEBP', 'JPEG'} and settings.target_kb and len(data) > settings.target_kb * 1024:
                # Find highest tested quality within the budget, keeping resolution fixed.
                trials = [(data, quality)]
                low, high = 25, quality - 1
                while low <= high:
                    if cancelled():
                        raise Cancelled()
                    mid = (low + high) // 2
                    trial = encode(image, fmt, mid)
                    trials.append((trial, mid))
                    if len(trial) <= settings.target_kb * 1024:
                        low = mid + 1
                    else:
                        high = mid - 1
                eligible = [item for item in trials if len(item[0]) <= settings.target_kb * 1024]
                data, quality = max(eligible, key=lambda item: item[1]) if eligible else min(trials, key=lambda item: len(item[0]))
            candidates.append((data, fmt, quality))
        except Cancelled:
            raise
        except (OSError, ValueError) as exc:
            errors.append(f'{fmt}: {exc}')
    if not candidates:
        raise ValueError('; '.join(errors) or 'Tidak ada encoder yang tersedia.')
    data, fmt, quality = min(candidates, key=lambda item: len(item[0]))
    if cancelled():
        raise Cancelled()
    folder.mkdir(parents=True, exist_ok=True)
    base = f'{source.stem}-web-{image.width}x{image.height}'
    number = 0
    extension = source.suffix if settings.format == 'ORIGINAL' else '.' + fmt.lower()
    while True:
        output = folder / f'{base}{"-" + str(number) if number else ""}{extension}'
        try:
            handle = output.open('xb')
            break
        except FileExistsError:
            number += 1
    try:
        with handle:
            handle.write(data)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return Result(str(source), str(output), source.stat().st_size, len(data), *original_size,
                  *image.size, fmt, quality,
                  not settings.target_kb or len(data) <= settings.target_kb * 1024)
