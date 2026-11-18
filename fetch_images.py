"""Скачивает картинки скинов в webapp/img (чтобы не зависеть от чужого сайта).
Запуск на своём компьютере: python fetch_images.py"""
import re, urllib.request
from pathlib import Path

src = Path(__file__).with_name("bot.py").read_text(encoding="utf-8")
base = re.search(r'BASE = "([^"]+)"', src).group(1)
files = re.findall(r'", "(?:blue|purple|pink|red|gold)", "([^"]+\.png)"', src)
out = Path(__file__).with_name("webapp") / "img"
out.mkdir(parents=True, exist_ok=True)
for f in files:
    req = urllib.request.Request(base + f, headers={"User-Agent": "Mozilla/5.0"})
    (out / f).write_bytes(urllib.request.urlopen(req, timeout=30).read())
    print("ok", f)
print(f"Готово: {len(files)} картинок в {out}")
