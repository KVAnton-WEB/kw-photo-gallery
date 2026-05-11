#!/usr/bin/env python3
"""
Генератор фотогалереи — только Python, без HTML/CSS/JS строк
"""
import subprocess
import argparse
from pathlib import Path
from PIL import Image, ImageOps, ExifTags
from concurrent.futures import ThreadPoolExecutor
import time
import shutil

SUPPORTED_TYPES = {'.jpg', '.jpeg', '.png'}
DEFAULT_MAX_SIZE = 2560
DEFAULT_THUMB_SIZE = 600
DEFAULT_QUALITY = 65

# === HTML шаблоны ===

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AntonKw Photo Gallery</title>
  <link rel="stylesheet" href="assets/photoswipe.css?v=1.0">
  <link rel="stylesheet" href="assets/style.css?v=1.0">
</head>
<body>
  <div class="header">
    <h1>📸 AntonKw Photo Gallery</h1>
    <p>{count} photos • Click for full view • HD button for original quality</p>
  </div>

  <div class="gallery" id="gallery">
{images}
  </div>

  <div class="footer">
    <p>© {year} • <a href="https://t.me/AntonKw" target="_blank">@AntonKw</a></p>
  </div>

  <script type="module" src="assets/kw-photo-gallery.js?v=1.0"></script>
</body>
</html>'''

IMAGE_TEMPLATE = '''    <a href="{avif}"
       data-pswp-width="{width}"
       data-pswp-height="{height}"
       data-raw="{raw}"
       data-download="{filename}.jpg">
      <img src="{thumb}"
           alt="{alt}"
           loading="lazy"
           width="600" height="400">
    </a>
'''


def parse_args():
    parser = argparse.ArgumentParser(description='Генератор статической фотогалереи')
    parser.add_argument('--root', type=str, default='.',
                        help='Корневая директория (по умолчанию: текущая)')
    parser.add_argument('--output', type=str, default=None,
                        help='Путь к index.html (по умолчанию: {root}/index.html)')
    parser.add_argument('--max-size', type=int, default=DEFAULT_MAX_SIZE,
                        help=f'Максимальный размер full (по умолчанию: {DEFAULT_MAX_SIZE})')
    parser.add_argument('--thumb-size', type=int, default=DEFAULT_THUMB_SIZE,
                        help=f'Размер превью (по умолчанию: {DEFAULT_THUMB_SIZE})')
    parser.add_argument('--quality', type=int, default=DEFAULT_QUALITY,
                        help=f'Качество AVIF (по умолчанию: {DEFAULT_QUALITY})')
    parser.add_argument('--workers', type=int, default=4,
                        help='Параллельных обработчиков (по умолчанию: 4)')
    parser.add_argument('--no-gpu', action='store_true', help='Отключить GPU')
    parser.add_argument('--force', action='store_true', help='Пересоздать все файлы')
    parser.add_argument('--dry-run', action='store_true', help='Только показать план')
    return parser.parse_args()


def check_tools():
    tools = {
        'vips': shutil.which('vipsthumbnail') is not None,
        'ffmpeg': shutil.which('ffmpeg') is not None,
        'vaapi': False,
    }
    if tools['ffmpeg']:
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
            if 'AMD' in result.stdout or 'Radeon' in result.stdout:
                tools['vaapi'] = True
        except:
            pass
    return tools


def find_images(raw_dir: Path) -> list[Path]:
    return sorted([
        f for f in raw_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_TYPES
    ])


def get_image_info(img_path: Path) -> tuple[int, int, Image.Image]:
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    return img.width, img.height, img


def calculate_size(w: int, h: int, max_size: int) -> tuple[int, int]:
    if w <= max_size and h <= max_size:
        return w, h
    if w >= h:
        return max_size, int(h * (max_size / w))
    return int(w * (max_size / h)), max_size


def make_thumbnail(img_path: Path, output_path: Path, img: Image.Image,
                   tools: dict, thumb_size: int):
    if tools['vips']:
        cmd = ['vips', 'thumbnail', str(img_path),
               str(output_path) + '[Q=75]', f'{thumb_size}x{thumb_size}']
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        thumb = img.copy()
        thumb.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
        thumb.save(output_path, 'WEBP', quality=75)


def make_avif(img_path: Path, output_path: Path, w: int, h: int,
              tools: dict, quality: int):
    if tools['ffmpeg']:
        scale = f'scale={w}:{h}:flags=lanczos'
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', str(img_path), '-vf', scale,
            '-c:v', 'libaom-av1',
            '-crf', str(max(10, int((100 - quality) / 2))),
            '-cpu-used', '5', '-frames:v', '1',
            '-pix_fmt', 'yuv420p', str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    else:
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img)
        if (w, h) != (img.width, img.height):
            img = img.resize((w, h), Image.Resampling.LANCZOS)
        img.save(output_path, 'AVIF', quality=quality)


def process_image(img_path: Path, full_dir: Path, thumb_dir: Path,
                  tools: dict, args, root: Path) -> dict | None:
    try:
        stem = img_path.stem
        print(f"  {img_path.name}...", end=" ", flush=True)

        width, height, img = get_image_info(img_path)

        # Превью
        thumb_path = thumb_dir / f"{stem}_thumb.webp"
        if args.force or not thumb_path.exists():
            make_thumbnail(img_path, thumb_path, img, tools, args.thumb_size)
            print("thumb✓", end=" ", flush=True)

        # AVIF
        avif_path = full_dir / f"{stem}.avif"
        new_w, new_h = calculate_size(width, height, args.max_size)
        if args.force or not avif_path.exists():
            make_avif(img_path, avif_path, new_w, new_h, tools, args.quality)
            print("avif✓", end=" ", flush=True)

        img.close()

        size_info = f"{new_w}x{new_h}" if (new_w, new_h) != (width, height) else "orig"
        print(f"({size_info})")

        return {
            'thumb': str(thumb_path.resolve().relative_to(root.resolve())),
            'avif': str(avif_path.resolve().relative_to(root.resolve())),
            'raw': str(img_path.resolve().relative_to(root.resolve())),
            'width': new_w,
            'height': new_h,
            'alt': stem,
            'filename': stem,
        }
    except Exception as e:
        print(f"✗ {e}")
        return None


def generate_html(images_data: list[dict], output_path: Path):
    images_html = '\n'.join(IMAGE_TEMPLATE.format(**img) for img in images_data)

    html = HTML_TEMPLATE.format(
        count=len(images_data),
        year=time.strftime('%Y'),
        images=images_html,
    )

    output_path.write_text(html, encoding='utf-8')
    print(f"✅ HTML: {output_path}")


def main():
    args = parse_args()
    tools = check_tools()

    root = Path(args.root).resolve()
    raw_dir = root / 'raw'
    full_dir = root / 'full'
    thumb_dir = root / 'thumbs'
    output_path = Path(args.output).resolve() if args.output else root / 'index.html'

    # Вывод конфигурации
    print(f"📁 Root:   {root}")
    print(f"📁 Output: {output_path}")
    print(f"⚙️  Max: {args.max_size}px | Thumb: {args.thumb_size}px | Q: {args.quality} | Workers: {args.workers}")
    print(f"🔧 vips: {'✅' if tools['vips'] else '❌'} | ffmpeg: {'✅' if tools['ffmpeg'] else '❌'} | GPU: {'✅' if tools['vaapi'] else '❌'}")
    print()

    if args.dry_run:
        raw_dir.mkdir(parents=True, exist_ok=True)
        images = find_images(raw_dir)
        print(f"📸 Found {len(images)} images (dry run)")
        return

    for d in [raw_dir, full_dir, thumb_dir]:
        d.mkdir(exist_ok=True)

    images = find_images(raw_dir)
    if not images:
        print("❌ No images found!")
        return

    print(f"📸 Processing {len(images)} images...\n")
    start = time.time()

    images_data = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_image, p, full_dir, thumb_dir, tools, args, root): p
            for p in images
        }
        for future in futures:
            result = future.result()
            if result:
                images_data.append(result)

    images_data.sort(key=lambda x: x['alt'])

    print(f"\n⏱️  Time: {time.time() - start:.1f}s")
    generate_html(images_data, output_path)
    print(f"✅ Done! {len(images_data)} photos → {output_path}")


if __name__ == '__main__':
    main()
