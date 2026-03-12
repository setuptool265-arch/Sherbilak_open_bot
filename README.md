# 🗳️ OpenBudget.uz — Ovoz Berish Boti (Captchasiz)

Foydalanuvchi faqat **telefon raqam** + **SMS kod** kiritadi.
Captcha umuman yo'q — API bevosita SMS yuboradi.

## Ishga tushirish

```bash
pip install -r requirements.txt
cp .env.example .env
# .env ga BOT_TOKEN yozing
python3 bot.py
```

## Jarayon

```
/start
  └─► Raqam so'raladi
        └─► Raqam yuboriladi
              └─► SMS keladi
                    └─► Kod kiritiladi
                          └─► ✅ Ovoz qabul qilindi
```

## Eslatma

Agar `send-code` endpoint ishlamasa, `bot.py` da
`SEND_CODE_URL` va `VOTE_URL` ni brauzer `F12 → Network`
orqali tekshirib yangilang.
