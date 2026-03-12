"""
openbudget.uz — Haqiqiy API endpointlarini topish uchun diagnostika.
Ishlatish: python3 find_api.py
"""

import asyncio
import aiohttp
import json

PHONE = "998949999819"
APPLICATION = "66b53e63-87bc-40b4-8fcc-e0f6da010ef9"
BOARD_ID = "53"
BASE = "https://openbudget.uz"

# Sinab ko'riladigan barcha mumkin endpointlar
CANDIDATES = [
    # bultakov/openbudget kutubxonasidagi variant
    f"{BASE}/api/v1/initiatives/{APPLICATION}/vote/send-code",
    # Boshqa ko'p uchraydigan variantlar
    f"{BASE}/api/v1/initiatives/{APPLICATION}/vote/send_code",
    f"{BASE}/api/v1/initiatives/{APPLICATION}/send-code",
    f"{BASE}/api/v1/initiatives/{APPLICATION}/sendCode",
    f"{BASE}/api/v1/vote/send-code",
    f"{BASE}/api/v1/vote/send_code",
    f"{BASE}/api/initiatives/{APPLICATION}/vote/send-code",
    f"{BASE}/api/initiatives/vote/send-code",
    # boards/initiatives pattern
    f"{BASE}/api/v1/boards/{BOARD_ID}/initiatives/{APPLICATION}/vote/send-code",
    f"{BASE}/api/v1/boards/{BOARD_ID}/initiatives/{APPLICATION}/send-code",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12) "
        "AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8",
    "Content-Type": "application/json",
    "Origin": BASE,
    "Referer": f"{BASE}/boards/initiatives/initiative/{BOARD_ID}/{APPLICATION}",
}

PAYLOADS = [
    {"phone": PHONE, "application": APPLICATION},
    {"phone": PHONE, "initiativeId": APPLICATION, "boardId": BOARD_ID},
    {"phone": PHONE, "initiative_id": APPLICATION},
    {"phone": f"+{PHONE}"},
]


async def test_endpoint(session: aiohttp.ClientSession, url: str, payload: dict):
    try:
        async with session.post(
            url,
            json=payload,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
            ssl=True,
        ) as resp:
            try:
                body = await resp.json(content_type=None)
            except Exception:
                body = await resp.text()
            return resp.status, body
    except aiohttp.ClientConnectorError:
        return "CONN_ERR", None
    except asyncio.TimeoutError:
        return "TIMEOUT", None
    except Exception as e:
        return f"ERR:{e}", None


async def main():
    print("=" * 60)
    print("openbudget.uz API Diagnostika")
    print("=" * 60)

    connector = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Avval sayt ochilishini tekshirish
        print("\n[1] Sayt aloqasi tekshirilmoqda...")
        try:
            async with session.get(
                BASE, timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                print(f"    {BASE} → HTTP {r.status}")
        except Exception as e:
            print(f"    {BASE} → XATO: {e}")

        # Har bir endpoint sinash
        print("\n[2] Endpointlar sinab ko'rilmoqda...\n")
        found = []

        for url in CANDIDATES:
            for payload in PAYLOADS:
                status, body = await test_endpoint(session, url, payload)

                # 200/201 = topildi, 400/422 = endpoint bor lekin payload xato
                # 404/405 = endpoint yo'q
                # 0/CONN = ulanish xatosi
                icon = "❓"
                if status in (200, 201):
                    icon = "✅ ISHLADI"
                    found.append((url, payload, status, body))
                elif status in (400, 401, 422):
                    icon = "⚠️  ENDPOINT BOR (payload xato)"
                    found.append((url, payload, status, body))
                elif status in (404, 405):
                    icon = "❌ YO'Q"
                else:
                    icon = f"🔴 {status}"

                print(f"  {icon}")
                print(f"    URL:     {url}")
                print(f"    Payload: {json.dumps(payload, ensure_ascii=False)}")
                if body and status not in (404, 405):
                    body_str = json.dumps(body, ensure_ascii=False)[:120]
                    print(f"    Javob:   {body_str}")
                print()

        print("=" * 60)
        print("XULOSA:")
        if found:
            print(f"\n✅ {len(found)} ta natija topildi:\n")
            for url, payload, status, body in found:
                print(f"  URL:     {url}")
                print(f"  Payload: {json.dumps(payload, ensure_ascii=False)}")
                print(f"  Status:  {status}")
                print(f"  Javob:   {str(body)[:200]}")
                print()
        else:
            print("\n❌ Hech qanday endpoint ishlamadi.")
            print("   Brauzerda F12 → Network orqali tekshiring.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
