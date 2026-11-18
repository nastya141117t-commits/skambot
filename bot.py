"""Рулетка скинов Blox Strike: Telegram-бот + Mini App + API.
Запуск: BOT_TOKEN="9154759609:AAEe2ofVRtTY156_Y5JEYqSnABDSoVioDYQ" WEBAPP_URL=https://твой-домен LOBBY_URL="https://roblox.com.bz/games/114234929420007/ZOMBIES-BloxStrike?privateServerLinkCode=06950255702508369675809703950614" python bot.py
"""
import asyncio, hashlib, hmac, json, os, random, secrets, time
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message, WebAppInfo)

TOKEN = "9154759609:AAEe2ofVRtTY156_Y5JEYqSnABDSoVioDYQ"
WEBAPP_URL = "https://google.com"
LOBBY_URL = "https://roblox.com.bz/games/114234929420007/ZOMBIES-BloxStrike?privateServerLinkCode=06950255702508369675809703950614"
COOLDOWN = int(os.getenv("COOLDOWN", 24 * 3600))   # 1 прокрутка в сутки
PORT = int(os.getenv("PORT", 8080))
DB_FILE = Path("db.json")
WEB_DIR = Path(__file__).parent / "webapp"

# Реальные скины Blox Strike (данные: bloxodes.com/wiki/bloxstrike/weapon-skins).
# Редкости в игре: blue < purple < pink < red; gold = «Forbidden» (самая редкая).
BASE = "https://media.bloxodes.com/wiki/7633926880/weapon-skins/"
RARITY_W = {"blue": 45, "purple": 30, "pink": 15, "red": 8, "gold": 2}   # шанс редкости, %
_RAW = [
    ("AK-47 | Red Baron", "blue", "ak-47-red-baron-851f0d84bfe28054.png"),
    ("M4A4 | Wrapped", "blue", "m4a4-wrapped-8f17191fb66b40f2.png"),
    ("Desert Eagle | Turbo", "blue", "desert-eagle-turbo-e202cae3f38accec.png"),
    ("Glock-18 | Broken TV", "blue", "glock-18-broken-tv-b86916ff9934aede.png"),
    ("USP-S | SpecOps", "blue", "usp-s-specops-69f4f7c93739060a.png"),
    ("AK-47 | Aniki", "purple", "ak-47-aniki-7ade6b80431032f9.png"),
    ("AK-47 | Rebellion", "purple", "ak-47-rebellion-132c0f6670f10a89.png"),
    ("Desert Eagle | Punk", "purple", "desert-eagle-punk-a29534f6a70df842.png"),
    ("Dual Berettas | Gilded", "purple", "dual-berettas-gilded-306236b7a9984a3c.png"),
    ("P250 | Zen", "purple", "p250-zen-9e768ecdd3c70c43.png"),
    ("M4A4 | BubblePop", "pink", "m4a4-bubblepop-833aa81322e97986.png"),
    ("Galil AR | Monochrome", "pink", "galil-ar-monochrome-6b4bda3a7ef73bf2.png"),
    ("Glock-18 | Fade", "pink", "glock-18-fade-0af670c228db9da6.png"),
    ("Desert Eagle | Mercy", "pink", "desert-eagle-mercy-e5e84ab0726da80f.png"),
    ("USP-S | Ajax", "pink", "usp-s-ajax-06fe9a6ee208fb6f.png"),
    ("AK-47 | Lore", "red", "ak-47-lore-1ead97e23722c31b.png"),
    ("AK-47 | Sakura", "red", "ak-47-sakura-5dc6f6be73dc0c85.png"),
    ("AK-47 | Luminex", "red", "ak-47-luminex-7954d581eea746a2.png"),
    ("M4A1-S | Retro", "red", "m4a1-s-retro-629ae4ffc8e087b5.png"),
    ("M4A4 | The Ambassador", "gold", "m4a4-the-ambassador-20465a1df675f5a7.png"),
]
IMG_DIR = WEB_DIR / "img"   # если скачать картинки (fetch_images.py), берутся локально
SKINS = [{"id": f"s{i}", "name": n, "r": r,
          "img": f"/img/{f}" if (IMG_DIR / f).exists() else BASE + f} for i, (n, r, f) in enumerate(_RAW)]
for s in SKINS:  # вес скина = шанс редкости / число скинов этой редкости
    s["w"] = RARITY_W[s["r"]] / sum(1 for x in SKINS if x["r"] == s["r"])
EMOJI = {"blue": "🔵", "purple": "🟣", "pink": "🩷", "red": "🔴", "gold": "🟡"}
RNAME = {"blue": "Синий", "purple": "Фиолетовый", "pink": "Розовый", "red": "Красный", "gold": "Запретный"}

db = json.loads(DB_FILE.read_text()) if DB_FILE.exists() else {}
def save(): DB_FILE.write_text(json.dumps(db, ensure_ascii=False))

def left_for(uid: int) -> int:
    last = db.get(str(uid), {}).get("last", 0)
    return max(0, int(last + COOLDOWN - time.time()))

def roll(uid: int):
    """Победитель выбирается ТОЛЬКО на сервере."""
    if left_for(uid):
        return None
    skin = random.choices(SKINS, weights=[s["w"] for s in SKINS])[0]
    code = "BS-" + secrets.token_hex(3).upper()
    u = db.setdefault(str(uid), {"prizes": []})
    u["last"] = time.time()
    u["prizes"].append({"skin": skin["id"], "code": code, "ts": time.time(), "claimed": False})
    save()
    return {"skin": skin, "code": code, "link": LOBBY_URL.format(code=code)}

def check_init(init: str):
    d = dict(parse_qsl(init, keep_blank_values=True))
    h = d.pop("hash", None)
    if not h:
        return None
    s = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(key, s.encode(), hashlib.sha256).hexdigest(), h):
        return None
    if time.time() - int(d.get("auth_date", 0)) > 86400:
        return None
    return json.loads(d["user"])["id"]

# ───────────── API для Mini App ─────────────
async def api_skins(_):
    return web.json_response([{k: s[k] for k in ("id", "name", "r", "w", "img")} for s in SKINS])

async def api_state(req):
    uid = check_init(req.headers.get("X-Init-Data", ""))
    if not uid:
        return web.json_response({"ok": False, "err": "auth"}, status=401)
    return web.json_response({"ok": True, "left": left_for(uid)})

async def api_spin(req):
    uid = check_init(req.headers.get("X-Init-Data", ""))
    if not uid:
        return web.json_response({"ok": False, "err": "auth"}, status=401)
    res = roll(uid)
    if not res:
        return web.json_response({"ok": False, "left": left_for(uid)})
    bot: Bot = req.app["bot"]
    try:  # дублируем приз в чат — не потеряется
        await bot.send_message(uid, f"🎁 Выпал скин: <b>{res['skin']['name']}</b> ({RNAME[res['skin']['r']]})\n"
                                    f"Код: <code>{res['code']}</code>", parse_mode="HTML",
                               reply_markup=claim_kb(res["link"]))
    except Exception:
        pass
    return web.json_response({"ok": True, **res})

# ───────────── Бот ─────────────
dp = Dispatcher()

def claim_kb(link):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Забрать в лобби", url=link)]])

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Открыть рулетку", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="⚡ Быстрая крутка в чате", callback_data="spin")],
    ])

def fmt(left):
    h, m = left // 3600, left % 3600 // 60
    return f"{h} ч {m} мин"

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🔫 <b>Рулетка скинов Blox Strike</b>\nКрути раз в сутки и забирай скин в игре.\n"
                   "Удачи, мой друг.", parse_mode="HTML", reply_markup=main_kb())

def frame(window):
    return f"🎰 <b>Blox Strike · Рулетка</b>\n\n⠀⠀⠀⠀⠀▼\n{''.join(window)}\n⠀⠀⠀⠀⠀▲"

@dp.callback_query(F.data == "spin")
async def spin_cb(c: CallbackQuery):
    uid = c.from_user.id
    res = roll(uid)
    if not res:
        await c.answer(f"Следующая крутка через {fmt(left_for(uid))}", show_alert=True)
        return
    await c.answer()
    win_idx, total, pad = 34, 42, 3
    allr = list(EMOJI.values())
    track = ["⬛"] * pad + [random.choice(allr) for _ in range(total)]
    track[pad + win_idx] = EMOJI[res["skin"]["r"]]
    msg = await c.message.answer(frame(track[:7]), parse_mode="HTML")
    F_N, last = 16, ""
    for k in range(1, F_N + 1):
        p = 1 - (1 - k / F_N) ** 3          # замедление
        pos = round(win_idx * p)
        txt = frame(track[pos:pos + 7])
        if txt != last:
            try:
                await msg.edit_text(txt, parse_mode="HTML")
            except TelegramBadRequest:
                pass
            last = txt
        await asyncio.sleep(0.25 + 0.06 * k)
    s = res["skin"]
    await msg.edit_text(
        f"{EMOJI[s['r']]} <b>{s['name']}</b> — {RNAME[s['r']]}\n\n"
        f"Код: <code>{res['code']}</code>\nЖми кнопку и заходи в лобби — бот выдаст скин.",
        parse_mode="HTML", reply_markup=claim_kb(res["link"]))

# ───────────── Запуск ─────────────
async def main():
    bot = Bot(TOKEN)
    app = web.Application()
    app["bot"] = bot
    app.add_routes([
        web.get("/", lambda _: web.FileResponse(WEB_DIR / "index.html")),
        web.get("/api/skins", api_skins),
        web.post("/api/state", api_state),
        web.post("/api/spin", api_spin),
    ])
    app.router.add_get("/health", lambda _: web.Response(text="ok"))   # для пингера (UptimeRobot)
    if IMG_DIR.exists():
        app.router.add_static("/img", IMG_DIR)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
