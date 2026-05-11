#!/usr/bin/env python3
"""
Генератор фотогалереи с быстрой обработкой
- GPU-декодирование через VAAPI
- Сохранение ориентации из EXIF
- AVIF full с ресайзом до 2560px
- WebP только для превью
"""
import subprocess
import argparse
from pathlib import Path
from PIL import Image, ImageOps, ExifTags
from concurrent.futures import ThreadPoolExecutor
import time
import shutil
import sys

SUPPORTED_TYPES = {'.jpg', '.jpeg', '.png'}
MAX_FULL_SIZE = 2560  # Максимальный размер для full AVIF

# Проверка доступности инструментов
HAS_VIPS = shutil.which('vipsthumbnail') is not None
HAS_FFMPEG = shutil.which('ffmpeg') is not None
HAS_VAAPI = False


print(f"🔧 Available tools:")
print(f"  vips:       {'✅' if HAS_VIPS else '❌ (using Pillow)'}")
print(f"  ffmpeg:     {'✅' if HAS_FFMPEG else '❌'}")
print(f"  GPU (VAAPI): {'✅' if HAS_VAAPI else '❌'}")

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Генератор статической фотогалереи',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s                                    # Всё в текущей директории
  %(prog)s --root ~/gallery                   # Указать корневую директорию
  %(prog)s --root ./input --output ./out.html # Свои пути
        """
    )

    parser.add_argument('--root', type=str, default='.',
                        help='Корневая директория галереи (raw/, full/, thumbs/ создаются внутри)')
    parser.add_argument('--output', type=str, default=None,
                        help='Путь к выходному HTML (по умолчанию: {root}/index.html)')

    parser.add_argument('--max-size', type=int, default=2560,
                        help='Максимальный размер full по большей стороне (по умолчанию: 2560)')
    parser.add_argument('--thumb-size', type=int, default=600,
                        help='Размер превью (по умолчанию: 600)')
    parser.add_argument('--quality', type=int, default=65,
                        help='Качество AVIF (по умолчанию: 65)')
    parser.add_argument('--workers', type=int, default=4,
                        help='Параллельных обработчиков (по умолчанию: 4)')
    parser.add_argument('--no-gpu', action='store_true',
                        help='Отключить GPU')
    parser.add_argument('--force', action='store_true',
                        help='Пересоздать все файлы')
    parser.add_argument('--dry-run', action='store_true',
                        help='Только показать план, без обработки')

    return parser.parse_args()

def check_tools():
    """Проверка доступных инструментов"""
    tools = {
        'vips': shutil.which('vipsthumbnail') is not None,
        'vips_full': shutil.which('vips') is not None,
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

def print_config(args, tools, raw_dir, full_dir, thumb_dir, output_path):
    """Вывод конфигурации"""
    print("=" * 60)
    print("📸 Photo Gallery Generator")
    print("=" * 60)
    print()
    print(f"📁 Root:     {Path(args.root).resolve()}")
    print(f"  Raw:       {raw_dir.resolve()}")
    print(f"  Full:      {full_dir.resolve()}")
    print(f"  Thumbs:    {thumb_dir.resolve()}")
    print(f"  Output:    {output_path.resolve()}")
    print()
    print(f"⚙️  Settings:")
    print(f"  Max size:  {args.max_size}px")
    print(f"  Thumb:     {args.thumb_size}px")
    print(f"  Quality:   {args.quality}")
    print(f"  Workers:   {args.workers}")
    print(f"  GPU:       {'❌ off' if args.no_gpu else '✅ on' if tools['vaapi'] else '⚠️  n/a'}")
    print(f"  Force:     {'✅ yes' if args.force else '❌ no'}")
    print(f"  Dry run:   {'✅ yes' if args.dry_run else '❌ no'}")
    print()

def find_images(raw_dir: Path) -> list[Path]:
    """Найти все изображения независимо от регистра расширения"""
    images = []
    for file in raw_dir.iterdir():
        if file.is_file() and file.suffix.lower() in SUPPORTED_TYPES:
            images.append(file)
    return sorted(images)


def get_image_info(img_path: Path) -> tuple[int, int, int, Image.Image]:
    """
    Получить размеры и изображение с правильной ориентацией.
    Возвращает: (ширина, высота, ориентация, PIL.Image)
    """
    img = Image.open(img_path)

    # Применяем ориентацию из EXIF
    img = ImageOps.exif_transpose(img)

    # Конвертируем в RGB если нужно
    if img.mode in ('RGBA', 'P', 'LA', 'CMYK'):
        img = img.convert('RGB')

    orientation = 0
    try:
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                if ExifTags.TAGS.get(tag) == 'Orientation':
                    orientation = value
                    break
    except:
        pass

    return img.width, img.height, orientation, img


def calculate_new_size(width: int, height: int, max_size: int) -> tuple[int, int]:
    """Рассчитать новые размеры, сохраняя пропорции"""
    if width <= max_size and height <= max_size:
        return width, height

    if width >= height:
        new_width = max_size
        new_height = int(height * (max_size / width))
    else:
        new_height = max_size
        new_width = int(width * (max_size / height))

    return new_width, new_height


def generate_thumbnail_vips(img_path: Path, output_path: Path, size: int = 600):
    """Генерация превью через vipsthumbnail (очень быстро)"""
    cmd = [
        'vips', 'thumbnail',
        str(img_path),
        str(output_path) + '[Q=75]',
        f'{size}x{size}'
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def generate_thumbnail_pillow(img: Image.Image, output_path: Path, size: tuple = (600, 400)):
    """Генерация превью через Pillow (запасной вариант)"""
    thumb = img.copy()
    thumb.thumbnail(size, Image.Resampling.LANCZOS)
    thumb.save(output_path, 'WEBP', quality=75)


def generate_avif_ffmpeg(img_path: Path, output_path: Path,
                         new_width: int, new_height: int, quality: int = 65):
    """Генерация AVIF через ffmpeg с GPU-декодированием"""

    scale_filter = f'scale={new_width}:{new_height}:flags=lanczos'

    if HAS_VAAPI:
        # GPU-декодирование + ресайз
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-hwaccel', 'vaapi',
            '-hwaccel_device', '/dev/dri/renderD128',
            '-hwaccel_output_format', 'vaapi',
            '-i', str(img_path),
            '-vf', f'scale_vaapi={new_width}:{new_height}',
            '-c:v', 'libaom-av1',
            '-crf', str(int((100 - quality) / 2)),
            '-cpu-used', '5',
            '-frames:v', '1',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
    else:
        # Программное декодирование
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', str(img_path),
            '-vf', scale_filter,
            '-c:v', 'libaom-av1',
            '-crf', str(int((100 - quality) / 2)),
            '-cpu-used', '5',
            '-frames:v', '1',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def generate_avif_pillow(img: Image.Image, output_path: Path,
                         new_width: int, new_height: int, quality: int = 65):
    """Генерация AVIF через Pillow (запасной вариант)"""
    if (new_width, new_height) != (img.width, img.height):
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    else:
        img_resized = img

    img_resized.save(output_path, 'AVIF', quality=quality)


def process_single_image(img_path: Path, full_dir: Path, thumb_dir: Path, tools: dict, args, root: Path) -> dict:
    """Обработка одного изображения"""
    try:
        stem = img_path.stem
        print(f"  {img_path.name}...")

        # 1. Получаем информацию об изображении с правильной ориентацией
        width, height, orientation, img = get_image_info(img_path)

        # 2. Генерируем превью WebP
        thumb_path = thumb_dir / f"{stem}_thumb.webp"
        if args.force or not thumb_path.exists():
          if not thumb_path.exists():
              if tools['vips']:
                  generate_thumbnail_vips(img_path, thumb_path)
                  print("vips✓", end=" ", flush=True)
              else:
                  generate_thumbnail_pillow(img, thumb_path)
                  print("pil✓", end=" ", flush=True)

        # 3. Генерируем full AVIF с ресайзом
        avif_path = full_dir / f"{stem}.avif"
        new_width, new_height = calculate_new_size(width, height, args.max_size)

        if args.force or not avif_path.exists():
            if tools['ffmpeg']:
                generate_avif_ffmpeg(img_path, avif_path, new_width, new_height)
                print("ff✓", end=" ", flush=True)
            else:
                generate_avif_pillow(img, avif_path, new_width, new_height)
                print("pil✓", end=" ", flush=True)

        img.close()
        size_str = f"{new_width}x{new_height}" if (new_width, new_height) != (width, height) else "orig"
        print(f"({size_str})")

        # Исправлено: пути относительно root, с проверкой
        try:
            thumb_rel = thumb_path.resolve().relative_to(root.resolve())
        except ValueError:
            # Если thumb не под root, используем относительный путь от output
            thumb_rel = thumb_path

        try:
            avif_rel = avif_path.resolve().relative_to(root.resolve())
        except ValueError:
            avif_rel = avif_path

        try:
            raw_rel = img_path.resolve().relative_to(root.resolve())
        except ValueError:
            raw_rel = img_path
        return {
            'thumb': str(thumb_rel),
            'avif': str(avif_rel),
            'raw': str(raw_rel),
            'width': new_width,
            'height': new_height,
            'alt': stem,
        }

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None


def generate_gallery():
    start_time = time.time()
    args = parse_args()
    tools = check_tools()

    # Корневая директория
    root = Path(args.root).resolve()
    # Поддиректории внутри root
    raw_dir = root / 'raw'
    full_dir = root / 'full'
    thumb_dir = root / 'thumbs'

        # Выходной HTML
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = root / 'index.html'


    print_config(args, tools, raw_dir, full_dir, thumb_dir, output_path)

    if args.dry_run:
        print("🔍 Dry run — File Validation...")
        raw_dir.mkdir(parents=True, exist_ok=True)
        images = find_images(raw_dir)
        print(f"📸 Found {len(images)} images")
        print("✅ Dry run Completed")
        return

    raw_dir.mkdir(exist_ok=True)
    full_dir.mkdir(exist_ok=True)
    thumb_dir.mkdir(exist_ok=True)

    # Поиск изображений
    print("\n🔍 Searching for images...")
    image_files = find_images(raw_dir)
    total = len(image_files)

    if total == 0:
        print("❌ No images found in 'raw' directory!")
        return

    print(f"📸 Found {total} images\n")

    images_data = []

    # Параллельная обработка
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_single_image, img_path, full_dir, thumb_dir, tools, args, root): img_path
            for img_path in image_files
        }

        for i, future in enumerate(futures, 1):
            result = future.result()
            if result:
                images_data.append(result)

    # Сортируем по имени
    images_data.sort(key=lambda x: x['alt'])

    elapsed = time.time() - start_time
    print(f"\n⏱️  Processing time: {elapsed:.1f}s")

    # Генерируем HTML (ваш оригинальный код)
    print("🔨 Generating HTML...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Photo Gallery</title>
  <link rel="stylesheet" href="photoswipe.css?v=1.0">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: grey; font-family: system-ui; }
    button.pswp__button--toggle-hd {
      font-size: 20px;
      color: #fff;
    }
    .gallery {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 4px;
      padding: 4px;
    }

    .gallery a {
      display: block;
      aspect-ratio: 3/2;
      overflow: hidden;
      content-visibility: auto;
      contain-intrinsic-size: 400px 267px;
    }

    .gallery img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      cursor: pointer;
      transition: transform 0.2s;
    }

    .gallery img:hover { transform: scale(1.03); }
  </style>
</head>
<body>
  <div class="gallery" id="gallery">
''')

        for img in images_data:
            f.write(f'''    <a href="{img['avif']}"
       data-pswp-width="{img['width']}"
       data-pswp-height="{img['height']}"
       data-raw="{img['raw']}"
       data-download="{img['alt']}.jpg">
      <img src="{img['thumb']}"
           alt="{img['alt']}"
           loading="lazy"
           width="600" height="400">
    </a>
''')

        # Ваш оригинальный JavaScript
        f.write('''  </div>

  <script type="module">
    import PhotoSwipeLightbox from './photoswipe-lightbox.esm.min.js?v=1.0';

    const lightbox = new PhotoSwipeLightbox({
      gallery: '#gallery',
      children: 'a',
      pswpModule: () => import('./photoswipe.esm.min.js?v=1.0'),
    });

    // Кнопка скачивания RAW
    lightbox.on('uiRegister', function() {
       lightbox.pswp.ui.registerElement({
          name: 'download-button',
          order: 8,
          isButton: true,
          tagName: 'a',

          // SVG with outline
          html: {
            isCustomSVG: true,
            inner: '<path d="M20.5 14.3 17.1 18V10h-2.2v7.9l-3.4-3.6L10 16l6 6.1 6-6.1ZM23 23H9v2h14Z" id="pswp__icn-download"/>',
            outlineID: 'pswp__icn-download'
          },

          onInit: (el, pswp) => {
            el.setAttribute('download', '');
            el.setAttribute('target', '_blank');
            el.setAttribute('rel', 'noopener');

            pswp.on('change', () => {
              const slide = pswp.currSlide;
              el.href = slide.data?.element?.dataset?.raw;
            });
          }
        });

      // Кнопка просмотра RAW (HD)
   lightbox.pswp.ui.registerElement({
        name: 'toggle-hd',
        order: 7,
        isButton: true,
        ariaLabel: 'Переключить качество',
        title: 'Переключить качество в HD/WEB',
        html: 'HD',

        onInit: (el, pswp) => {
          // Сбрасываем кнопку при смене слайда
          pswp.on('change', () => {
            el.innerHTML = 'HD';
            el.style.fontWeight = 'normal';
          });
        },

        onClick: (event, el) => {
          const pswp = lightbox.pswp;
          const slide = pswp.currSlide;
          const element = slide.data.element;
          const rawUrl = element?.dataset?.raw;
          const fullUrl = element?.href; // AVIF

          if (!rawUrl || !fullUrl) return;

          const isHD = slide.data._isHD;
          const newSrc = isHD ? fullUrl : rawUrl;

          // Показать индикатор загрузки
          pswp.dispatch('loadingIndicatorDisplay', { isDisplayed: true });

          // Предзагрузка изображения
          const img = new Image();
          img.onload = () => {
            const currentImg = slide.content.element;
            if (currentImg) {
              // Плавная смена
              currentImg.style.transition = 'opacity 0.3s ease';
              currentImg.style.opacity = '0';

              setTimeout(() => {
                currentImg.src = newSrc;
                currentImg.onload = () => {
                  currentImg.style.opacity = '1';
                  slide.data._isHD = !isHD;
                  slide.data.src = newSrc;

                  // Обновить кнопку
                  el.innerHTML = slide.data._isHD ? 'WEB' : 'HD';
                  el.style.fontWeight = slide.data._isHD ? 'bold' : 'normal';
                };
              }, 300);
            }

            pswp.dispatch('loadingIndicatorDisplay', { isDisplayed: false });
          };

          img.onerror = () => {
            console.error('Failed to load HD image');
            pswp.dispatch('loadingIndicatorDisplay', { isDisplayed: false });
          };

          img.src = newSrc;
        }
      });
    });

    lightbox.init();
  </script>
</body>
</html>''')

    print(f"✅ Сгенерировано {len(images_data)} изображений")
    print(f"📁 gallery.html готов")


if __name__ == '__main__':
    generate_gallery()
