# Telegram Bot O'rnatish — Biznes Pro

## 1. Supabase da jadval qo'shish

Supabase → SQL Editor ga kiring, `supabase_sql.sql` faylidagi kodni ishga tushiring.

## 2. Admin ID ni aniqlash

Telegramda botingizga `/id` yuboring — raqam chiqadi.
`bot.py` da `ADMIN_CHAT_ID = None` o'rniga o'sha raqamni yozing.

## 3. Railway da joylashtirish (BEPUL)

1. **https://railway.app** → GitHub bilan kiring
2. **"New Project"** → **"Deploy from GitHub repo"**
3. Bu papkani GitHub ga yuklang (yoki ZIP dan yuklash)
4. Railway avtomatik ishga tushiradi

### GitHub ga yuklash (birinchi marta):

```bash
git init
git add .
git commit -m "Biznes Pro bot"
git remote add origin https://github.com/SIZNING/repo.git
git push -u origin main
```

## 4. Ishlatish

Diller:
1. Botga `/start` yuboradi
2. Ism + telefon kiritadi
3. Siz tasdiqlaysiz: `/approve_DILLER_ID`
4. Diller mahsulot tanlab zakaz beradi
5. Siz Biznes Pro → Dillerlar da ko'rasiz

## Bot buyruqlari

- `/start` — boshlash
- `/id` — chat ID ko'rish (admin uchun)
- `/approve_123456789` — dillerni tasdiqlash
