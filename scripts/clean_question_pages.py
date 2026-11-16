"""Remove the pale red watermark before running local OCR."""

from pathlib import Path
from PIL import Image
import numpy as np

root = Path(__file__).resolve().parents[1]
src = root / "tmp" / "question_bank_pages"
dst = root / "tmp" / "question_bank_pages_clean"
dst.mkdir(exist_ok=True)

for path in sorted(src.glob("page-*.jpg")):
    out = dst / path.name
    if out.exists():
        continue
    pixels = np.array(Image.open(path).convert("RGB"))
    r, g, b = (pixels[:, :, i].astype(np.int16) for i in range(3))
    watermark = (r > g + 25) & (r > b + 18) & (r > 130)
    pixels[watermark] = 255
    Image.fromarray(pixels).save(out, quality=95)
    print(path.name)
