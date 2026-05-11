#!/usr/bin/env python3
"""
Генератор фотогалереи — с красивым прогресс-баром
"""
import subprocess
import argparse
from pathlib import Path
from PIL import Image, ImageOps
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import shutil
import sys
import threading
import zipfile

SUPPORTED_TYPES = {'.jpg', '.jpeg', '.png'}
DEFAULT_MAX_SIZE = 2560
DEFAULT_THUMB_SIZE = 600
DEFAULT_QUALITY = 65

def minify_assets(assets_dir: Path):
    """Минифицировать JS и CSS если есть terser/cssnano"""
    js_file = assets_dir / 'kw-photo-gallery.js'
    css_file = assets_dir / 'style.css'

    # Проверяем terser
    if shutil.which('npx'):
        try:
            # Минификация JS
            subprocess.run([
                'npx', 'terser',
                str(js_file),
                '-o', str(assets_dir / 'kw-photo-gallery.min.js'),
                '-c', '-m'
            ], check=True, capture_output=True)
            print(f"✅ JS minified: kw-photo-gallery.min.js")
        except:
            pass

# Блокировка для синхронизации вывода
print_lock = threading.Lock()

TEMPLATES_DIR = Path(__file__).parent / 'tpl'

def load_template(name: str) -> str:
    """Загрузить шаблон из файла"""
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding='utf-8')

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
    parser.add_argument('--no-zip', action='store_true',
                    help='Не создавать ZIP архив')
    parser.add_argument('--no-gpu', action='store_true', help='Отключить GPU')
    parser.add_argument('--force', action='store_true', help='Пересоздать все файлы')
    parser.add_argument('--dry-run', action='store_true', help='Только показать план')
    parser.add_argument('--author-name', type=str, default=None, help='Имя владельца галереи')
    parser.add_argument('--author-link', type=str, default=None, help='Контакты ссылка')
    parser.add_argument('--author-title', type=str, default=None, help='Контакты заголовок ссылки')


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

def create_raw_archive(raw_dir: Path, output_path: Path, prefix, force: bool = False) -> Path | None:
    """
    Создать ZIP-архив из всех raw-файлов.
    Возвращает путь к архиву или None.
    """
    archive_path = output_path / f'{prefix}_PhotoGallery_raw.zip'

    if archive_path.exists() and not force:
        print(f"📦 Archive already exists: {archive_path}")
        return archive_path

    raw_files = sorted([
        f for f in raw_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_TYPES
    ])

    if not raw_files:
        print("⚠️  No raw files for archive")
        return None

    print(f"📦 Creating archive with {len(raw_files)} files...")

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, file_path in enumerate(raw_files, 1):
            zf.write(file_path, file_path.name)
            # Прогресс каждые 50 файлов
            if i % 50 == 0 or i == len(raw_files):
                print(f"  Added {i}/{len(raw_files)}: {file_path.name}")

    size_mb = archive_path.stat().st_size / 1024 / 1024
    print(f"📦 Archive created: {archive_path} ({size_mb:.1f} MB)")

    return archive_path


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
                   tools: dict, thumb_size: int) -> str:
    """Возвращает статус: 'vips', 'pil', 'skip', 'err'"""
    if output_path.exists():
        return 'skip'

    try:
        if tools['vips']:
            cmd = ['vips', 'thumbnail', str(img_path),
                   str(output_path) + '[Q=75]', f'{thumb_size}x{thumb_size}']
            subprocess.run(cmd, check=True, capture_output=True)
            return 'vips'
        else:
            thumb = img.copy()
            thumb.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
            thumb.save(output_path, 'WEBP', quality=75)
            return 'pil'
    except Exception:
        return 'err'


def make_avif(img_path: Path, output_path: Path, w: int, h: int,
              tools: dict, quality: int) -> str:
    """Возвращает статус: 'ffmpeg', 'pil', 'skip', 'err'"""
    if output_path.exists():
        return 'skip'

    try:
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
            return 'ffmpeg'
        else:
            img = Image.open(img_path)
            img = ImageOps.exif_transpose(img)
            if (w, h) != (img.width, img.height):
                img = img.resize((w, h), Image.Resampling.LANCZOS)
            img.save(output_path, 'AVIF', quality=quality)
            return 'pil'
    except Exception:
        return 'err'


def process_image(img_path: Path, full_dir: Path, thumb_dir: Path,
                  tools: dict, args, root: Path) -> dict | None:
    """Обработка одного изображения. Тихо, без вывода."""
    try:
        stem = img_path.stem
        width, height, img = get_image_info(img_path)

        # Превью
        thumb_path = thumb_dir / f"{stem}_thumb.webp"
        thumb_status = 'skip'
        if args.force or not thumb_path.exists():
            thumb_status = make_thumbnail(img_path, thumb_path, img, tools, args.thumb_size)

        # AVIF
        avif_path = full_dir / f"{stem}.avif"
        new_w, new_h = calculate_size(width, height, args.max_size)
        avif_status = 'skip'
        if args.force or not avif_path.exists():
            avif_status = make_avif(img_path, avif_path, new_w, new_h, tools, args.quality)

        img.close()

        size_info = f"{new_w}×{new_h}" if (new_w, new_h) != (width, height) else "orig"

        return {
            'thumb': str(thumb_path.resolve().relative_to(root.resolve())),
            'avif': str(avif_path.resolve().relative_to(root.resolve())),
            'raw': str(img_path.resolve().relative_to(root.resolve())),
            'width': new_w,
            'height': new_h,
            'alt': stem,
            'filename': stem,
            # Для лога
            'name': img_path.name,
            'size_info': size_info,
            'thumb_status': thumb_status,
            'avif_status': avif_status,
        }
    except Exception as e:
        return {
            'error': str(e),
            'name': img_path.name,
        }


def print_progress(current: int, total: int, elapsed: float,
                   current_file: str = '', status: str = ''):
    """Вывод прогресс-бара с восстановлением цвета"""
    pct = current / total * 100
    bar_width = 25
    filled = int(bar_width * current / total)
    bar = '█' * filled + '░' * (bar_width - filled)

    eta = ''
    if current > 0:
        eta_sec = elapsed / current * (total - current)
        if eta_sec > 60:
            eta = f'ETA: {eta_sec/60:.0f}m'
        else:
            eta = f'ETA: {eta_sec:.0f}s'

    elapsed_str = f'{elapsed:.0f}s' if elapsed < 60 else f'{elapsed/60:.1f}m'

    file_part = f' | {current_file}' if current_file else ''
    status_part = f' | {status}' if status else ''

    # \033[0m — сброс всех атрибутов цвета
    line = f'\r\033[0m  [{bar}] {pct:5.1f}% ({current}/{total}) | {elapsed_str} | {eta}{file_part}{status_part}\033[K'

    sys.stdout.write(line)
    sys.stdout.flush()


def main():
    args = parse_args()
    tools = check_tools()

    root = Path(args.root).resolve()
    raw_dir = root / 'raw'
    full_dir = root / 'full'
    thumb_dir = root / 'thumbs'
    output_path = Path(args.output).resolve() if args.output else root / 'index.html'

    # Вывод конфигурации
    print()
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

    total = len(images)
    print(f"📸 Processing {total} images...\n")
    start = time.time()

    images_data = []
    errors = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_image, p, full_dir, thumb_dir, tools, args, root): p
            for p in images
        }

        completed = 0
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            elapsed = time.time() - start

            if result:
                if 'error' in result:
                    errors.append(result)
                    status = f'❌ {result["error"][:40]}'
                else:
                    images_data.append(result)
                    # Формируем статус
                    parts = []
                    if result['thumb_status'] not in ('skip',):
                        parts.append(f"thumb:{result['thumb_status']}")
                    if result['avif_status'] not in ('skip',):
                        parts.append(f"avif:{result['avif_status']}")
                    status = ' | '.join(parts) if parts else '⏭️ cached'
                    status += f' [{result["size_info"]}]'

                # Выводим прогресс
                print_progress(completed, total, elapsed, result['name'], status)


    # Финальный перевод строки
    print()

    elapsed = time.time() - start

    # Статистика
    print(f"\n{'='*60}")
    print(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/total:.1f}s per image)")
    print(f"✅ Success: {len(images_data)}")
    if errors:
        print(f"❌ Errors:  {len(errors)}")
        for e in errors:
            print(f"   - {e['name']}: {e['error']}")
    print()

    # Создание ZIP архива
    archive_path = None
    if not args.no_zip:
        archive_path = create_raw_archive(raw_dir, root, args.author_name, args.force)

    # Сортируем и генерируем HTML
    images_data.sort(key=lambda x: x['alt'])
    generate_html(images_data, output_path, archive_path, args)
    minify_assets(root / 'assets')
    print(f"✅ Done! {len(images_data)} photos → {output_path}")
    sys.stdout.write('\033[0m\n')
    sys.stdout.flush()


def generate_html(images_data: list[dict], output_path: Path, archive_path, args):
    image_template = load_template('img.html')
    index_template = load_template('main.html')
    footer_template = load_template('footer.html')

    images_html = '\n'.join(image_template.format(**img) for img in images_data)

    # Архивная ссылка
    if archive_path:
        archive_size = archive_path.stat().st_size / 1024 / 1024
        archive_link = f'<p class="archive-link">📦 <a href="{args.author_name}_PhotoGallery_raw.zip" download>Скачать весь архив в исходном качестве</a> ({archive_size:.0f} MB)</p>'
    else:
        archive_link = ''

    html = index_template.format(
        count=len(images_data),
        year=time.strftime('%Y'),
        images=images_html,
        archive=archive_link,
        footer=footer_template.format(
            link=args.author_link,
            title=args.author_title
        ),
        author_name=args.author_name
    )

    output_path.write_text(html, encoding='utf-8')
    print(f"📄 HTML: {output_path}")


if __name__ == '__main__':
    main()
