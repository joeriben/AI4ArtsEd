#!/usr/bin/env python3
"""
Resize config-preview originals into 300x300 bubble images for the preset overlay.

Reads full-size originals from  resources/config-preview-originals/<config_id>.png
(gitignored source assets, kept on the dev host) and writes 300x300 previews to
public/ai4artsed-frontend/public/config-previews/<config_id>.webp (committed,
served to the frontend via config-previews/<config_id>.webp).

WebP at 95 rather than PNG: a 300x300 photograph costs about 145 KB as a PNG
and about 33 KB this way, and one ring of the perspective chooser loads six or
seven of them at once. At the size a circle shows them the two are the same
picture.

Usage:
    python3 scripts/resize_new_backgrounds.py
"""

from PIL import Image
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ORIGINALS_DIR = PROJECT_ROOT / 'resources/config-preview-originals'
PREVIEW_DIR = PROJECT_ROOT / 'public/ai4artsed-frontend/public/config-previews'

# Settings
TARGET_SIZE = (300, 300)
WEBP_QUALITY = 95

# Config IDs to (re)generate previews for. Each needs an original at
# ORIGINALS_DIR/<config_id>.png; output is written to PREVIEW_DIR/<config_id>.webp.
CONFIGS_TO_PROCESS = [
    'aesthetic',
]

def resize_image(input_path, output_path):
    """Resize and optimize a single image to TARGET_SIZE."""
    print(f'Processing: {input_path.name}')

    with Image.open(input_path) as img:
        # Flatten transparency onto white (previews are opaque)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        print(f'  Original: {img.size[0]}x{img.size[1]}')

        img_resized = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        img_resized.save(output_path, 'WEBP', quality=WEBP_QUALITY, method=6)

    input_size = input_path.stat().st_size
    output_size = output_path.stat().st_size
    reduction = ((input_size - output_size) / input_size) * 100
    print(f'  Output: {TARGET_SIZE[0]}x{TARGET_SIZE[1]}')
    print(f'  Size: {input_size/1024/1024:.2f}M -> {output_size/1024:.0f}KB ({reduction:.1f}% reduction)')
    print()

def main():
    print('=' * 70)
    print('RESIZE CONFIG-PREVIEW ORIGINALS -> 300x300 BUBBLES')
    print('=' * 70)
    print()

    processed = 0
    missing = []
    for config_id in CONFIGS_TO_PROCESS:
        input_path = ORIGINALS_DIR / f'{config_id}.png'
        if input_path.exists():
            resize_image(input_path, PREVIEW_DIR / f'{config_id}.webp')
            print(f'OK {config_id} preview updated')
            processed += 1
        else:
            print(f'SKIP {input_path} not found')
            missing.append(config_id)

    print('=' * 70)
    print(f'{processed}/{len(CONFIGS_TO_PROCESS)} previews written')
    if missing:
        print(f'MISSING originals: {", ".join(missing)}')
    print('=' * 70)

if __name__ == '__main__':
    main()
