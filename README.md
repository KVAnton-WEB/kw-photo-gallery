# 📸 KW Photo Gallery ⚡🎈🪶🚲🍃

**Static photo gallery generator for photographers.**
Build once, host anywhere — even on a router.

## Concept

You shoot photos. You want to share them with clients or friends.
You don't want a database, a backend, or a slow site.

KW Photo Gallery takes a folder of RAW photos and generates a **fully static website**:

- **Thumbnails** — lightweight WebP · lazy-loaded · responsive grid
- **Preview** — compressed AVIF (limited to 2560px) · instant viewing
- **Original** — full-resolution JPEG · one click to download or view in HD

Everything is pre-generated on your PC. The result is pure static HTML + CSS + JS.
No server-side code, no API, no database. Copy the `web/` folder to any server and you're done.

## Why

| Feature | What it means |
|---------|---------------|
| **Zero server load** | Nginx serves static files. That's it. |
| **Tiny resource usage** | ~5 MB RAM, <0.1 CPU at idle. Runs on OpenWRT routers, Raspberry Pi, NAS. |
| **Modern compression** | AVIF for previews (30-50% smaller than JPEG), WebP for thumbnails. |
| **Original quality** | Clients can view HD or download full JPEGs. |
| **GPU-accelerated build** | Uses VAAPI/ffmpeg/vips for fast image processing. |
| **Lazy loading** | Browsers load only visible images. |
| **Mobile-first** | Touch gestures, fullscreen mode, responsive grid. |
| **No vendor lock-in** | You own all files. Host anywhere — GitHub Pages, VPS, router, S3 bucket. |

## Why WebP for thumbnails, not AVIF?

AVIF is great for full-size previews — excellent compression, small files. But for thumbnails (600px, ~15-20 KB each), the file size difference is negligible. What matters more is **decoding speed**:  AVIF 2-3× slower

With lazy-loaded thumbnails, you want them to appear **instantly** as the user scrolls. WebP decodes faster on mobile devices, making the gallery feel snappier. For the full preview (where you look at one image at a time), the slightly slower AVIF decode is worth the bandwidth savings.

## How It Works

```
raw/                    full/                  thumbs/
├── photo1.jpg    →     ├── photo1.avif        ├── photo1_thumb.webp
├── photo2.JPG    →     ├── photo2.avif        ├── photo2_thumb.webp
└── ...                 └── ...                └── ...
                                        ↘
                                    index.html
                                    (static, ready to serve)
```

1. Drop your photos into `web/raw/`
2. Run the generator
3. Copy `web/` to any web server
4. Done

## Installation

### Prerequisites

**Required:**
- Python 3.10+
- Pillow (for image processing fallback)

**Recommended (massive speed boost):**
- libvips + vipsthumbnail (fast thumbnails, ~3x faster)
- ffmpeg + libaom (AVIF encoding, GPU support via VAAPI)

```bash
# Ubuntu/Debian
sudo apt install python3-pil libvips-tools ffmpeg

# macOS
brew install python vips ffmpeg
pip3 install Pillow
```

## Quick Start

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Put your photos in web/raw/
mkdir -p web/raw
cp /path/to/photos/*.jpg web/raw/

# Generate the gallery
python3 generate_gallery.py --root ./web --author-name "Your Name or Title" --author-link "https://your.site" --author-title @AntonKw

# Preview locally
python3 -m http.server 8080 --directory web/
# Open http://localhost:8080
```

## Options

```bash
python3 generate_gallery.py \
  --root ./web \                # Project root (default: current dir)
  --max-size 2560 \             # Max preview dimension (default: 2560px)
  --thumb-size 600 \            # Thumbnail size (default: 600px)
  --quality 65 \                # AVIF quality (default: 65)
  --workers 4 \                 # Parallel processing threads
  --no-gpu \                    # Disable GPU acceleration
  --force \                     # Regenerate all files
  --no-zip \                    # Skip creating raw_archive.zip
  --dry-run                     # preview without processing
  --author-name "Jane Doe" \    # Name for the gallery header
  --author-link "https://..."   # Clickable link in footer
  --author-title "ex@mail.com"  # Clickable link in footer
```

## Deployment

### Option 1: Docker + Nginx (recommended)

```bash
docker compose up -d
# Gallery available at http://localhost:8080
```

### Option 2: Any static file server

Copy the web/ folder to your server:

```bash
scp -r web/ user@server:/var/www/gallery/
```

## Project Structure

```text
.
├── generate_gallery.py        # Main generator script
├── requirements.txt           # Python dependencies
├── nginx.conf                 # Optimized nginx config
├── docker-compose.yml         # Docker setup
├── tpl/                       # HTML templates
│   ├── main.html              # Main page template
│   ├── img.html               # Single image template
│   └── footer.html            # Footer template
├── web/                       # Generated static site (deploy this!)
│   ├── index.html             # Gallery page
│   ├── raw/                   # Original photos
│   ├── full/                  # AVIF previews
│   ├── thumbs/                # WebP thumbnails
│   ├── assets/                # CSS, JS, icons
│   └── AntonKw_PhotoGallery_raw.zip  # All originals archive
└── venv/                      # Virtual environment (gitignored)
```

## Features

### For Viewers

- Responsive grid layout, works on any screen
- Touch gestures (swipe, pinch-to-zoom)
- HD/WEB toggle — view compressed or original quality
- One-click download of original photos
- Image rotation
- Fullscreen mode (hides mobile address bar)
- Keyboard navigation (arrows, Escape)

### For Builders

- GPU-accelerated image processing (VAAPI) *
- Parallel processing (configurable workers)
- Preserves EXIF orientation
- Auto-resizes previews (configurable max dimension)
- Generates ZIP archive of all originals
- Custom author branding in header/footer
- Dry-run mode to preview without processing
- Progress bar with ETA

---

\* VAAPI GPU acceleration code is included but **untested and currently disabled**. My AMD card doesn't support hardware AV1 encoding, so I couldn't verify it. If you have a compatible GPU and want to tinker — the code is there. PRs welcome.

### For Hosting

- Pure static files — no backend, no database
- Nginx config with gzip, caching, sendfile
- Docker image: ~10MB (nginx:alpine)
- Memory usage: ~5MB at idle
- Works on anything that can serve files

## Browser Support

All modern browsers (Chrome, Firefox, Safari, Edge — 2020+).

## Libraries

- [PhotoSwipe 5](https://photoswipe.com/) — image viewer (MIT)
- [Pillow](https://python-pillow.github.io/) — image processing (PIL)
- [libvips](https://www.libvips.org/) — fast image processing (optional, LGPL)
- [ffmpeg](https://ffmpeg.org/) — AVIF encoding (optional, GPL)

## License

MIT — do whatever you want with it.

---

⚡🎈🪶🍃 *This is a pet project. A weekend project. A "vibe coding" thing. I couldn't find a static gallery generator that would compress images, provide the source files, be as simple as a bicycle, and run on my grandma's teapot.. Decided it's better to learn to read than to ask mom. So I did.*
