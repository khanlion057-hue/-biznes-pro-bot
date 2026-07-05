"""
BIZNES PRO — Telegram Bot (Dillerlar uchun)
Supabase SDK o'rniga to'g'ridan-to'g'ri HTTP ishlatiladi
"""

import json, asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ═══════════════════════════════════════
SUPABASE_URL = "https://amrauwymzjwdnaaspatk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFtcmF1d3ltemp3ZG5hYXNwYXRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMxMzc3MzIsImV4cCI6MjA5ODcxMzczMn0.kIyQvzEP8RlnfNfIM3r_PYaOX26Xp9P1-5Te_rSDgTE"
BOT_TOKEN   = "8427154380:AAFRn_ytuo55TQc_XEhEYbSTJvKDw6CdHiI"
ADMIN_CHAT_ID = 56944519
# ═══════════════════════════════════════

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def db_get(table, eq=None, select="*", limit=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if eq:
        for k, v in eq.items():
            url += f"&{k}=eq.{v}"
    if limit:
        url += f"&limit={limit}"
    r = httpx.get(url, headers=HEADERS, timeout=10)
    return r.json()

def db_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = httpx.post(url, headers=HEADERS, json=data, timeout=10)
    return r.status_code < 300

def db_update(table, eq, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    for k, v in eq.items():
        url += f"?{k}=eq.{v}"
    r = httpx.patch(url, headers=HEADERS, json=data, timeout=10)
    return r.status_code < 300

def get_app_data():
    rows = db_get("app_data", eq={"id": "main"})
    if rows and isinstance(rows, list) and rows[0].get("data"):
        return rows[0]["data"]
    return {}

def get_products():
    data = get_app_data()
    return data.get("products", [])

def get_stock(pid, data=None):
    if data is None:
        data = get_app_data()
    batches = data.get("batches", [])
    return sum(
        b["qty"] - b.get("sold", 0)
        for b in batches
        if b["pid"] == pid
        and b.get("status") not in ("empty", "transit")
        and b["qty"] - b.get("sold", 0) > 0
    )

def get_opt_price(product, data=None):
    if data is None:
        data = get_app_data()
    batches = data.get("batches", [])
    pid = product["id"]
    active = sorted(
        [b for b in batches if b["pid"] == pid and b.get("status") == "active" and b["qty"] - b.get("sold", 0) > 0],
        key=lambda b: b.get("date", "")
    )
    if not active:
        return 0
    cost = active[0].get("costUsd", 0)
    opt_pct = product.get("optMarkupPct", 15)
    return round(cost * (1 + opt_pct / 100), 2)

def fmt_usd(n):
    return f"${n:,.2f}"

def get_dealer(chat_id):
    rows = db_get("bot_dealers", eq={"chat_id": chat_id})
    return rows[0] if rows and isinstance(rows, list) and rows else None

def is_approved(chat_id):
    d = get_dealer(chat_id)
    return bool(d and d.get("approved"))

carts = {}
states = {}

def main_menu():
    return ReplyKeyboardMarkup([
        ["📦 Mahsulotlar", "🔍 Qidiruv"],
        ["🛒 Savat", "📋 Zakazlarim"],
    ], resize_keyboard=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dealer = get_dealer(chat_id)
    if dealer and dealer.get("approved"):
        await update.message.reply_text(
            f"👋 Xush kelibsiz, *{dealer['name']}*!",
            parse_mode="Markdown", reply_markup=main_menu()
        )
    elif dealer:
        await update.message.reply_text("⏳ Arizangiz ko'rib chiqilmoqda.")
    else:
        states[chat_id] = "waiting_name"
        await update.message.reply_text(
            "👋 Salom! Ro'yxatdan o'tish uchun *ismingizni* yuboring:",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if states.get(chat_id) == "waiting_name":
        states[chat_id] = "waiting_phone"
        ctx.user_data["reg_name"] = text
        await update.message.reply_text(f"Rahmat, *{text}*! Telefon raqamingiz (+998...):", parse_mode="Markdown")
        return

    if states.get(chat_id) == "waiting_phone":
        name = ctx.user_data.get("reg_name", "Noma'lum")
        db_insert("bot_dealers", {"chat_id": chat_id, "name": name, "phone": text, "approved": False})
        del states[chat_id]
        await update.message.reply_text("✅ Ariza yuborildi! Administrator tasdiqlagunicha kuting.")
        try:
            await ctx.bot.send_message(
                ADMIN_CHAT_ID,
                f"🆕 Yangi diller:\n*{name}* | {text}\n\nTasdiqlash: /approve_{chat_id}",
                parse_mode="Markdown"
            )
        except:
            pass
        return

    if states.get(chat_id) == "searching":
        del states[chat_id]
        await search_products(update, ctx, text)
        return

    if not is_approved(chat_id):
        await update.message.reply_text("⏳ Hali tasdiqlanmagan.")
        return

    if text == "📦 Mahsulotlar":
        await show_categories(update, ctx)
    elif text == "🔍 Qidiruv":
        states[chat_id] = "searching"
        await update.message.reply_text("🔍 Kod yoki nom yuboring:")
    elif text == "🛒 Savat":
        await show_cart(update, ctx)
    elif text == "📋 Zakazlarim":
        await show_orders(update, ctx)

async def show_categories(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    products = get_products()
    cats = sorted(set(p.get("cat", "Boshqa") for p in products if p.get("cat")))
    if not cats:
        await update.message.reply_text("😔 Mahsulotlar yo'q.")
        return
    keyboard = [[InlineKeyboardButton(f"📂 {c}", callback_data=f"cat:{c}")] for c in cats]
    await update.message.reply_text("📂 Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def search_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE, query: str):
    data = get_app_data()
    q = query.lower()
    results = [p for p in data.get("products", []) if q in p.get("sku","").lower() or q in p.get("name","").lower()]
    if not results:
        await update.message.reply_text("😔 Topilmadi.")
        return
    keyboard = []
    for p in results[:10]:
        stock = get_stock(p["id"], data)
        price = get_opt_price(p, data)
        keyboard.append([InlineKeyboardButton(f"{p['sku']} — {p['name'][:20]} | {fmt_usd(price)} | {stock}d", callback_data=f"prod:{p['id']}")])
    await update.message.reply_text(f"🔍 {len(results[:10])} ta topildi:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_cart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cart = carts.get(chat_id, {})
    if not cart:
        msg = "🛒 Savat bo'sh."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    data = get_app_data()
    products = data.get("products", [])
    total, text, keyboard = 0, "🛒 *Savat:*\n\n", []
    for pid, qty in cart.items():
        p = next((x for x in products if x["id"] == int(pid)), None)
        if not p: continue
        price = get_opt_price(p, data)
        line = price * qty
        total += line
        text += f"• {p['sku']} — {p['name'][:20]}\n  {qty} × {fmt_usd(price)} = *{fmt_usd(line)}*\n"
        keyboard.append([InlineKeyboardButton(f"❌ {p['sku']} ({qty}d)", callback_data=f"remove:{pid}")])
    text += f"\n💰 *Jami: {fmt_usd(total)}*"
    keyboard.append([InlineKeyboardButton("✅ ZAKAZ BERISH", callback_data="order:confirm")])
    keyboard.append([InlineKeyboardButton("🗑 Tozalash", callback_data="order:clear")])
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    orders = db_get("bot_orders", eq={"dealer_chat_id": chat_id})
    if not orders or not isinstance(orders, list):
        await update.message.reply_text("📋 Hali zakaz yo'q.")
        return
    text = "📋 *Zakazlaringiz:*\n\n"
    for o in orders[:10]:
        icon = {"new":"🆕","confirmed":"✅","shipped":"🚚"}.get(o.get("status",""),"❓")
        items = o.get("items", [])
        text += f"{icon} #{o['id']} — {o.get('created_at','')[:10]}\n   {len(items)} xil — *{fmt_usd(o.get('total_usd',0))}*\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.from_user.id
    data_str = q.data

    if not is_approved(chat_id):
        await q.answer("⏳ Tasdiqlanmagan", show_alert=True)
        return

    if data_str.startswith("cat:"):
        cat = data_str[4:]
        data = get_app_data()
        products = [p for p in data.get("products", []) if p.get("cat") == cat]
        keyboard = []
        for p in products:
            stock = get_stock(p["id"], data)
            if stock <= 0: continue
            price = get_opt_price(p, data)
            keyboard.append([InlineKeyboardButton(f"{p['sku']} — {p['name'][:25]} | {fmt_usd(price)} | {stock}d", callback_data=f"prod:{p['id']}")])
        if not keyboard:
            await q.edit_message_text("😔 Bu kategoriyada tovar yo'q.")
            return
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back:cats")])
        await q.edit_message_text(f"📂 *{cat}*\n\nMahsulotni tanlang:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data_str.startswith("prod:"):
        pid = int(data_str[5:])
        data = get_app_data()
        p = next((x for x in data.get("products", []) if x["id"] == pid), None)
        if not p: return
        stock = get_stock(pid, data)
        price = get_opt_price(p, data)
        text = f"📦 *{p['name']}*\nKod: `{p['sku']}`\n\n💲 *Opt narx: {fmt_usd(price)}*\n📊 Omborda: *{stock} dona*"
        keyboard = [
            [InlineKeyboardButton("➕ 1", callback_data=f"add:{pid}:1"),
             InlineKeyboardButton("➕ 5", callback_data=f"add:{pid}:5"),
             InlineKeyboardButton("➕ 10", callback_data=f"add:{pid}:10")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat:{p.get('cat','')}")]
        ]
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data_str.startswith("add:"):
        _, pid_str, qty_str = data_str.split(":")
        pid, qty = int(pid_str), int(qty_str)
        cart = carts.setdefault(chat_id, {})
        cart[str(pid)] = cart.get(str(pid), 0) + qty
        data = get_app_data()
        p = next((x for x in data.get("products", []) if x["id"] == pid), None)
        price = get_opt_price(p, data) if p else 0
        total_qty = cart[str(pid)]
        await q.answer(f"✅ +{qty} qo'shildi. Savat: {total_qty}d = {fmt_usd(price*total_qty)}")

    elif data_str.startswith("remove:"):
        pid = data_str[7:]
        cart = carts.get(chat_id, {})
        if pid in cart: del cart[pid]
        await show_cart(update, ctx)

    elif data_str == "order:clear":
        carts[chat_id] = {}
        await q.edit_message_text("🗑 Savat tozalandi.")

    elif data_str == "order:confirm":
        await place_order(update, ctx)

    elif data_str == "back:cats":
        products = get_products()
        cats = sorted(set(p.get("cat", "Boshqa") for p in products))
        keyboard = [[InlineKeyboardButton(f"📂 {c}", callback_data=f"cat:{c}")] for c in cats]
        await q.edit_message_text("📂 Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def place_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.from_user.id
    cart = carts.get(chat_id, {})
    if not cart:
        await update.callback_query.answer("Savat bo'sh!", show_alert=True)
        return
    dealer = get_dealer(chat_id)
    data = get_app_data()
    products = data.get("products", [])
    items, total = [], 0
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        p = next((x for x in products if x["id"] == pid), None)
        if not p: continue
        price = get_opt_price(p, data)
        line = price * qty
        total += line
        items.append({"pid": pid, "sku": p["sku"], "name": p["name"], "qty": qty, "price_usd": price, "line_usd": line})

    ok = db_insert("bot_orders", {
        "dealer_id": str(chat_id),
        "dealer_name": dealer["name"] if dealer else "Noma'lum",
        "dealer_chat_id": chat_id,
        "items": items,
        "total_usd": total,
        "status": "new"
    })
    if not ok:
        await update.callback_query.edit_message_text("❌ Xato yuz berdi. Qayta urinib ko'ring.")
        return
    carts[chat_id] = {}
    try:
        items_text = "\n".join([f"• {i['sku']} ×{i['qty']} = {fmt_usd(i['line_usd'])}" for i in items])
        dealer_name = dealer["name"] if dealer else "Noma'lum"
        await ctx.bot.send_message(
            ADMIN_CHAT_ID,
            f"🆕 *Yangi zakaz!*\nDiller: *{dealer_name}*\n\n{items_text}\n\n💰 Jami: *{fmt_usd(total)}*",
            parse_mode="Markdown"
        )
    except:
        pass
    await update.callback_query.edit_message_text(
        f"✅ *Zakaz qabul qilindi!*\n\n{len(items)} xil mahsulot\n💰 Jami: *{fmt_usd(total)}*",
        parse_mode="Markdown"
    )

async def approve_dealer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        dealer_chat_id = int(update.message.text.split("_")[1])
        db_update("bot_dealers", {"chat_id": dealer_chat_id}, {"approved": True})
        dealer = get_dealer(dealer_chat_id)
        await update.message.reply_text(f"✅ {dealer['name'] if dealer else dealer_chat_id} tasdiqlandi!")
        await ctx.bot.send_message(dealer_chat_id, "✅ *Siz tasdiqlandi!*\n\n/start bosing.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"), approve_dealer))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
