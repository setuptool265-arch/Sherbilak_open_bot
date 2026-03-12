"""
OpenBudget.uz — Ovoz Berish Telegram Boti
Captcha YO'Q — to'g'ridan API ga so'rov yuboriladi
SSL yoqilgan, barcha mumkin endpointlar sinab ko'riladi
"""

import asyncio
import logging
import os
import re
import ssl

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ─────────────────────────────────────────────
#  SOZLAMALAR
# ─────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

APPLICATION = "66b53e63-87bc-40b4-8fcc-e0f6da010ef9"
BOARD_ID    = "53"
BASE_URL    = "https://openbudget.uz"

INITIATIVE_LINK = (
    f"{BASE_URL}/boards/initiatives/initiative/{BOARD_ID}/{APPLICATION}"
)

# Barcha mumkin API endpointlar — ketma-ket sinab ko'riladi
SEND_CODE_VARIANTS = [
    f"{BASE_URL}/api/v1/initiatives/{APPLICATION}/vote/send-code",
    f"{BASE_URL}/api/v1/initiatives/{APPLICATION}/vote/send_code",
    f"{BASE_URL}/api/v1/boards/{BOARD_ID}/initiatives/{APPLICATION}/vote/send-code",
    f"{BASE_URL}/api/v1/boards/{BOARD_ID}/initiatives/{APPLICATION}/send-code",
    f"{BASE_URL}/api/v1/vote/send-code",
    f"{BASE_URL}/api/initiatives/{APPLICATION}/vote/send-code",
]

VOTE_VARIANTS = [
    f"{BASE_URL}/api/v1/initiatives/{APPLICATION}/vote",
    f"{BASE_URL}/api/v1/boards/{BOARD_ID}/initiatives/{APPLICATION}/vote",
    f"{BASE_URL}/api/v1/vote",
    f"{BASE_URL}/api/initiatives/{APPLICATION}/vote",
]

SEND_PAYLOADS = [
    lambda p: {"phone": p, "application": APPLICATION},
    lambda p: {"phone": p, "initiativeId": APPLICATION, "boardId": BOARD_ID},
    lambda p: {"phone": p, "initiative_id": APPLICATION},
    lambda p: {"phone": p},
]

VOTE_PAYLOADS = [
    lambda p, t, c: {"phone": p, "token": t, "code": c, "application": APPLICATION},
    lambda p, t, c: {"phone": p, "token": t, "code": c},
    lambda p, t, c: {"phone": p, "smsCode": c, "token": t},
    lambda p, t, c: {"phone": p, "code": c, "token": t, "initiativeId": APPLICATION},
]

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  FSM
# ─────────────────────────────────────────────
class VS(StatesGroup):
    waiting_phone = State()
    waiting_code  = State()


# ─────────────────────────────────────────────
#  YORDAMCHI
# ─────────────────────────────────────────────
def format_phone(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    if d.startswith("998") and len(d) == 12:
        return d
    if d.startswith("8") and len(d) == 11:
        return f"99{d[1:]}"
    if len(d) == 9:
        return f"998{d}"
    return d


def is_valid_phone(raw: str) -> bool:
    d = re.sub(r"\D", "", raw)
    if d.startswith("998") and len(d) == 12:
        return True
    if len(d) == 9 and d[0] in "3791456":
        return True
    return False


# ─────────────────────────────────────────────
#  OPENBUDGET API
# ─────────────────────────────────────────────
class OpenBudgetAPI:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Mobile Safari/537.36"
        ),
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8",
        "Content-Type":    "application/json",
        "Origin":          BASE_URL,
        "Referer":         INITIATIVE_LINK,
    }

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _post(self, url: str, payload: dict) -> tuple:
        try:
            async with self.session.post(
                url,
                json=payload,
                headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = {"raw": await resp.text()}
                logger.info(f"POST {url} [{resp.status}] → {str(data)[:200]}")
                return resp.status, data
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Ulanish xatosi {url}: {e}")
            return 0, {"message": "Ulanib bolmadi"}
        except asyncio.TimeoutError:
            logger.error(f"Timeout {url}")
            return 0, {"message": "Vaqt tugadi"}
        except Exception as e:
            logger.error(f"Xato {url}: {e}")
            return 0, {"message": str(e)}

    async def send_code(self, phone: str) -> dict:
        for url in SEND_CODE_VARIANTS:
            for payload_fn in SEND_PAYLOADS:
                payload = payload_fn(phone)
                status, data = await self._post(url, payload)

                if status in (200, 201):
                    logger.info(f"ISHLAGAN send_code URL: {url}")
                    return {"status": status, "data": data}

                if status == 409:
                    return {"status": 409, "data": data}

                if status in (400, 422):
                    body_str = str(data).lower()
                    if any(w in body_str for w in ("already", "voted", "ovoz", "exist")):
                        return {"status": 409, "data": data}
                    continue

                if status in (404, 405):
                    break

                if status == 0:
                    break

        return {"status": 0, "data": {"message": "Server bilan boglanib bolmadi"}}

    async def vote(self, phone: str, token: str, code: str) -> dict:
        for url in VOTE_VARIANTS:
            for payload_fn in VOTE_PAYLOADS:
                payload = payload_fn(phone, token, code)
                status, data = await self._post(url, payload)

                if status in (200, 201):
                    logger.info(f"ISHLAGAN vote URL: {url}")
                    return {"status": status, "data": data}

                if status in (400, 422):
                    err = str(data).lower()
                    if any(w in err for w in ("expired", "invalid", "wrong", "code", "token")):
                        return {"status": status, "data": data}
                    continue

                if status in (404, 405):
                    break

                if status == 0:
                    break

        return {"status": 0, "data": {"message": "Server bilan boglanib bolmadi"}}


# ─────────────────────────────────────────────
#  GLOBAL
# ─────────────────────────────────────────────
http_session: aiohttp.ClientSession = None  # type: ignore
router = Router()


def api() -> OpenBudgetAPI:
    return OpenBudgetAPI(http_session)


# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "🗳️ <b>Ochiq Byudjet — Ovoz Berish</b>\n\n"
        "📌 Loyiha: Mahalla va ko'chalar obodonlashtirish\n"
        f"🔗 <a href='{INITIATIVE_LINK}'>Loyihani ko'rish</a>\n\n"
        "1️⃣ Telefon raqamingizni yuboring\n"
        "2️⃣ SMS orqali kelgan kodni kiriting\n"
        "3️⃣ Ovozingiz qabul qilinadi ✅\n\n"
        "<i>⚠️ Har bir fuqaro faqat 1 marta ovoz bera oladi</i>",
        reply_markup=kb,
    )
    await state.set_state(VS.waiting_phone)


@router.message(VS.waiting_phone)
async def handle_phone(message: Message, state: FSMContext) -> None:
    if message.contact:
        raw_phone = message.contact.phone_number
    else:
        raw_phone = (message.text or "").strip()
        if not raw_phone:
            await message.answer("❌ Telefon raqamingizni yuboring!")
            return
        if not is_valid_phone(raw_phone):
            await message.answer(
                "❌ <b>Noto'g'ri raqam!</b>\n\n"
                "Misol: <code>901234567</code> yoki <code>+998901234567</code>"
            )
            return

    phone = format_phone(raw_phone)

    await message.answer(
        f"📱 Raqam: <code>+{phone}</code>\n\n⏳ SMS kod yuborilmoqda...",
        reply_markup=ReplyKeyboardRemove(),
    )

    result = await api().send_code(phone)
    status = result["status"]
    data   = result["data"]

    logger.info(f"send_code: user={message.from_user.id} phone={phone} status={status}")

    if status in (200, 201):
        token = (
            data.get("token")
            or data.get("sessionToken")
            or data.get("session_token")
            or ""
        )
        await state.update_data(phone=phone, token=token)
        await message.answer(
            "📩 <b>SMS yuborildi!</b>\n\n"
            f"📱 <code>+{phone}</code> raqamiga SMS keldi.\n\n"
            "👇 Kodni kiriting:"
        )
        await state.set_state(VS.waiting_code)

    elif status == 409:
        await message.answer(
            "⚠️ <b>Siz allaqachon ovoz bergansiz!</b>\n\n"
            "Har bir fuqaro faqat 1 marta ovoz bera oladi."
        )
        await state.clear()

    elif status == 429:
        await message.answer(
            "⏰ <b>Juda ko'p urinish!</b>\n\nBir oz kutib qayta urinib ko'ring."
        )
        await state.clear()

    elif status == 0:
        await message.answer(
            "🌐 <b>Server bilan bog'lanib bo'lmadi.</b>\n\n"
            "Keyinroq urinib ko'ring: /start"
        )
        await state.clear()

    else:
        err = data.get("message") or "Noma'lum xato"
        await message.answer(f"❌ Xatolik ({status}): {err}\n\nQayta: /start")
        await state.clear()


@router.message(VS.waiting_code)
async def handle_code(message: Message, state: FSMContext) -> None:
    code = re.sub(r"\D", "", (message.text or "").strip())
    if len(code) < 4:
        await message.answer("❌ Kod kamida 4 ta raqam!\n\nQayta kiriting:")
        return

    data  = await state.get_data()
    phone = data.get("phone", "")
    token = data.get("token", "")

    await message.answer("⏳ Ovoz berilmoqda...")

    result = await api().vote(phone, token, code)
    status = result["status"]
    rdata  = result["data"]

    logger.info(f"vote: user={message.from_user.id} status={status}")

    if status in (200, 201):
        await message.answer(
            "🎉 <b>OVOZINGIZ QABUL QILINDI!</b>\n\n"
            "✅ Muvaffaqiyatli ovoz berdingiz!\n\n"
            f"🔗 <a href='{INITIATIVE_LINK}'>Natijalarni ko'rish</a>\n\n"
            "🙏 Ishtirokingiz uchun rahmat!"
        )
        await state.clear()
        return

    if status == 400:
        err = rdata.get("message") or rdata.get("error") or ""
        if any(w in err.lower() for w in ("expired", "muddati", "timeout")):
            await message.answer("⏰ <b>Kod muddati o'tgan!</b>\n\nQayta: /start")
            await state.clear()
        else:
            await message.answer(f"❌ <b>Noto'g'ri kod!</b> {err}\n\nQayta kiriting:")
        return

    if status == 409:
        await message.answer("⚠️ Bu raqam bilan allaqachon ovoz berilgan!")
    elif status == 0:
        await message.answer("🌐 Server bilan bog'lanib bo'lmadi. Qayta: /start")
    else:
        err = rdata.get("message") or "Noma'lum xatolik"
        await message.answer(
            f"❌ Ovoz qabul qilinmadi ({status})\nSabab: {err}\n\nQayta: /start"
        )
    await state.clear()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "/start — Boshlash\n\n"
        "1. Telefon raqamni yuboring\n"
        "2. SMSdagi kodni kiriting\n"
        "3. Ovoz qabul qilinadi ✅"
    )


@router.message()
async def handle_unknown(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("👋 Ovoz berish uchun /start bosing!")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
async def main() -> None:
    global http_session

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    ssl_ctx = ssl.create_default_context()
    connector = aiohttp.TCPConnector(limit=300, limit_per_host=100, ssl=ssl_ctx)
    http_session = aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=20),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Bot ishga tushdi")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await http_session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
