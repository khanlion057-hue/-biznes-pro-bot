"""
BIZNES PRO — Telegram Bot (Dillerlar uchun)
Diller zakaz beradi → Biznes Pro da ko'rinadi
"""

import os, json, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from supabase import create_client

# ═══════════════════════════════════════
# SOZLAMALAR — o'zgartiring!
# ═══════════════════════════════════════
BOT_TOKEN    = "8427154380:AAFRn_ytuo55TQc_XEhEYbSTJvKDw6CdHiI"
SUPABASE_URL = "https://amrauwymzjwdnaaspatk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFtcmF1d3ltemp3ZG5hYXNwYXRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMxMzc3MzIsImV4cCI6MjA5ODcxMzczMn0.kIyQvzEP8RlnfNfIM3r_PYaOX26Xp9P1-5Te_rSDgTE"
ADMIN_CHAT_ID = 56944519  # Sizning Telegram ID
# ═══════════════════════════════════════

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# Foydalanuvchi savatlari (xotirada)
carts = {}
states = {}


def get_app_data():
    """Biznes Pro dan mahsulotlar va dillerlarni olish"""
    try:
        res = db.table("app_data").select("data").eq("id", "main").maybe_single().execute()
        return res.data["data"] if res.data else {}
    except:
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
    """Opt narxini hisoblash"""
    if data is None:
        data = get_app_data()
    batches = data.get("batches", [])
    pid = product["id"]
    # FIFO tannarx
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


def is_approved(chat_id):
    try:
        res = db.table("bot_dealers").select("approved").eq("chat_id", chat_id).maybe_single().execute()
        return res.data and res.data.get("approved", False)
    except:
        return False


def get_dealer(chat_id):
    try:
        res = db.table("bot_dealers").select("*").eq("chat_id", chat_id).maybe_single().execute()
        return res.data
    except:
        return None


def main_menu():
    return ReplyKeyboardMarkup([
        ["📦 Mahsulotlar", "🔍 Qidiruv"],
        ["🛒 Savat", "📋 Zakazlarim"],
        ["ℹ️ Yordam"]
    ], resize_keyboard=True)


# ═══════════════════════════════════════
# HANDLERLAR
# ═══════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dealer = get_dealer(chat_id)

    if dealer and dealer.get("approved"):
        await update.message.reply_text(
            f"👋 Xush kelibsiz, *{dealer['name']}*!\n\nQuyidagi menyudan foydalaning:",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    elif dealer and not dealer.get("approved"):
        await update.message.reply_text(
            "⏳ Sizning arizangiz ko'rib chiqilmoqda.\n"
            "Administrator tasdiqlagunicha kuting."
        )
    else:
        states[chat_id] = "waiting_name"
        await update.message.reply_text(
            "👋 Salom! *Biznes Pro* bot ga xush kelibsiz.\n\n"
            "Ro'yxatdan o'tish uchun *ismingizni* yuboring:",
            parse_mode="Markdown"
        )


async def handle_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin uchun chat ID ko'rish"""
    await update.message.reply_text(f"Sizning ID: `{update.effective_chat.id}`", parse_mode="Markdown")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Ro'yxatdan o'tish jarayoni
    if states.get(chat_id) == "waiting_name":
        states[chat_id] = "waiting_phone"
        ctx.user_data["reg_name"] = text
        await update.message.reply_text(f"Rahmat, *{text}*! Endi telefon raqamingizni yuboring (+998...):", parse_mode="Markdown")
        return

    if states.get(chat_id) == "waiting_phone":
        name = ctx.user_data.get("reg_name", "Noma'lum")
        phone = text
        try:
            db.table("bot_dealers").upsert({
                "chat_id": chat_id,
                "name": name,
                "phone": phone,
                "approved": False
            }).execute()
        except:
            pass
        del states[chat_id]
        await update.message.reply_text(
            "✅ Ariza yuborildi!\n\n"
            "Administrator sizni tasdiqlagunicha biroz kuting.\n"
            "Odatda 1-2 soat ichida tasdiqlash keladi."
        )
        # Adminga xabar
        if ADMIN_CHAT_ID:
            try:
                await ctx.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"🆕 Yangi diller arizada:\n"
                    f"*Ism:* {name}\n*Tel:* {phone}\n*ID:* {chat_id}\n\n"
                    f"Tasdiqlash uchun: /approve_{chat_id}",
                    parse_mode="Markdown"
                )
            except:
                pass
        return

    # Qidiruv holati
    if states.get(chat_id) == "searching":
        del states[chat_id]
        await search_products(update, ctx, text)
        return

    # Tasdiqlanmagan foydalanuvchi
    if not is_approved(chat_id):
        await update.message.reply_text("⏳ Sizning arizangiz hali tasdiqlanmagan.")
        return

    # Asosiy menyu
    if text == "📦 Mahsulotlar":
        await show_categories(update, ctx)
    elif text == "🔍 Qidiruv":
        states[chat_id] = "searching"
        await update.message.reply_text("🔍 Mahsulot kodi yoki nomini yuboring:")
    elif text == "🛒 Savat":
        await show_cart(update, ctx)
    elif text == "📋 Zakazlarim":
        await show_orders(update, ctx)
    elif text == "ℹ️ Yordam":
        await update.message.reply_text(
            "📌 *Qo'llanma:*\n\n"
            "1️⃣ *Mahsulotlar* → kategoriya tanlang → mahsulot tanlang → miqdor kiriting\n"
            "2️⃣ *Savat* → zakaz bering\n"
            "3️⃣ *Zakazlarim* → yuborilgan zakazlar\n\n"
            "❓ Savol bo'lsa administratorga murojaat qiling.",
            parse_mode="Markdown"
        )


async def show_categories(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    products = get_products()
    cats = list(set(p.get("cat", "Boshqa") for p in products if p.get("cat")))
    cats.sort()

    if not cats:
        await update.message.reply_text("😔 Mahsulotlar hali kiritilmagan.")
        return

    keyboard = [[InlineKeyboardButton(f"📂 {c}", callback_data=f"cat:{c}")] for c in cats]
    await update.message.reply_text(
        "📂 *Kategoriyani tanlang:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_products_by_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE, cat: str):
    data = get_app_data()
    products = data.get("products", [])
    cat_products = [p for p in products if p.get("cat") == cat]

    if not cat_products:
        await update.callback_query.answer("Bu kategoriyada mahsulot yo'q")
        return

    text = f"📂 *{cat}*\n\n"
    keyboard = []
    for p in cat_products:
        stock = get_stock(p["id"], data)
        price = get_opt_price(p, data)
        if stock <= 0:
            continue
        label = f"{p['sku']} — {p['name'][:25]} | {fmt_usd(price)} | {stock} dona"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"prod:{p['id']}")])

    if not keyboard:
        await update.callback_query.edit_message_text("😔 Bu kategoriyada hozirda tovar yo'q.")
        return

    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back:cats")])
    await update.callback_query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_product_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE, pid: int):
    data = get_app_data()
    products = data.get("products", [])
    p = next((x for x in products if x["id"] == pid), None)
    if not p:
        await update.callback_query.answer("Mahsulot topilmadi")
        return

    stock = get_stock(pid, data)
    price = get_opt_price(p, data)

    text = (
        f"📦 *{p['name']}*\n"
        f"Kod: `{p['sku']}`\n"
        f"Kategoriya: {p.get('cat', '—')}\n\n"
        f"💲 *Opt narx: {fmt_usd(price)}*\n"
        f"📊 Omborda: *{stock} dona*\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("➕ 1", callback_data=f"add:{pid}:1"),
            InlineKeyboardButton("➕ 5", callback_data=f"add:{pid}:5"),
            InlineKeyboardButton("➕ 10", callback_data=f"add:{pid}:10"),
        ],
        [InlineKeyboardButton("✏️ Miqdor kiriting", callback_data=f"qty:{pid}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat:{p.get('cat','')}")],
    ]

    await update.callback_query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def search_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE, query: str):
    data = get_app_data()
    products = data.get("products", [])
    q = query.lower()
    results = [
        p for p in products
        if q in p.get("sku", "").lower() or q in p.get("name", "").lower()
    ]

    if not results:
        await update.message.reply_text("😔 Topilmadi. Boshqa kalit so'z bilan qidiring.")
        return

    keyboard = []
    for p in results[:10]:
        stock = get_stock(p["id"], data)
        price = get_opt_price(p, data)
        label = f"{p['sku']} — {p['name'][:20]} | {fmt_usd(price)} | {stock}d"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"prod:{p['id']}")])

    await update.message.reply_text(
        f"🔍 *'{query}'* bo'yicha {len(results[:10])} ta topildi:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_cart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cart = carts.get(chat_id, {})

    if not cart:
        msg = "🛒 Savat bo'sh.\n\n📦 Mahsulotlar bo'limidan tanlang."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    data = get_app_data()
    products = data.get("products", [])
    total = 0
    text = "🛒 *Savat:*\n\n"
    keyboard = []

    for pid, qty in cart.items():
        p = next((x for x in products if x["id"] == int(pid)), None)
        if not p:
            continue
        price = get_opt_price(p, data)
        line = price * qty
        total += line
        text += f"• {p['sku']} — {p['name'][:20]}\n  {qty} × {fmt_usd(price)} = *{fmt_usd(line)}*\n"
        keyboard.append([InlineKeyboardButton(f"❌ {p['sku']} ({qty}d)", callback_data=f"remove:{pid}")])

    text += f"\n💰 *Jami: {fmt_usd(total)}*"
    keyboard.append([InlineKeyboardButton("✅ ZAKAZ BERISH", callback_data="order:confirm")])
    keyboard.append([InlineKeyboardButton("🗑 Savatni tozalash", callback_data="order:clear")])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        res = db.table("bot_orders").select("*").eq("dealer_chat_id", chat_id).order("created_at", desc=True).limit(10).execute()
        orders = res.data or []
    except:
        orders = []

    if not orders:
        await update.message.reply_text("📋 Hali zakaz yo'q.")
        return

    text = "📋 *So'nggi zakazlaringiz:*\n\n"
    for o in orders:
        status_icon = {"new": "🆕", "confirmed": "✅", "shipped": "🚚", "done": "✔️"}.get(o["status"], "❓")
        items = o.get("items", [])
        cnt = sum(i.get("qty", 0) for i in items)
        text += (
            f"{status_icon} #{o['id']} — {o['created_at'][:10]}\n"
            f"   {len(items)} xil, {cnt} dona — *{fmt_usd(o['total_usd'])}*\n\n"
        )

    await update.message.reply_text(text, parse_mode="Markdown")


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.from_user.id
    data_str = q.data

    if not is_approved(chat_id):
        await q.answer("⏳ Hali tasdiqlanmagan", show_alert=True)
        return

    if data_str.startswith("cat:"):
        cat = data_str[4:]
        if cat == "cats" or cat == "":
            await show_categories_edit(update, ctx)
        else:
            await show_products_by_cat(update, ctx, cat)

    elif data_str.startswith("prod:"):
        pid = int(data_str[5:])
        await show_product_detail(update, ctx, pid)

    elif data_str.startswith("add:"):
        _, pid_str, qty_str = data_str.split(":")
        pid = int(pid_str)
        qty = int(qty_str)
        cart = carts.setdefault(chat_id, {})
        cart[str(pid)] = cart.get(str(pid), 0) + qty
        data = get_app_data()
        products = data.get("products", [])
        p = next((x for x in products if x["id"] == pid), None)
        total_qty = cart[str(pid)]
        price = get_opt_price(p, data) if p else 0
        await q.answer(f"✅ +{qty} qo'shildi. Savatlda: {total_qty} dona ({fmt_usd(price*total_qty)})")

    elif data_str.startswith("qty:"):
        pid = data_str[4:]
        states[chat_id] = f"qty_input:{pid}"
        await q.edit_message_text(f"✏️ Mahsulot uchun miqdorni yozing (dona):")

    elif data_str.startswith("remove:"):
        pid = data_str[7:]
        cart = carts.get(chat_id, {})
        if pid in cart:
            del cart[pid]
        await show_cart(update, ctx)

    elif data_str == "order:clear":
        carts[chat_id] = {}
        await q.edit_message_text("🗑 Savat tozalandi.")

    elif data_str == "order:confirm":
        await place_order(update, ctx)

    elif data_str.startswith("back:"):
        if data_str == "back:cats":
            await show_categories_edit(update, ctx)


async def show_categories_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    products = get_products()
    cats = sorted(set(p.get("cat", "Boshqa") for p in products))
    keyboard = [[InlineKeyboardButton(f"📂 {c}", callback_data=f"cat:{c}")] for c in cats]
    await update.callback_query.edit_message_text(
        "📂 *Kategoriyani tanlang:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def place_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.from_user.id
    cart = carts.get(chat_id, {})
    if not cart:
        await update.callback_query.answer("Savat bo'sh!", show_alert=True)
        return

    dealer = get_dealer(chat_id)
    data = get_app_data()
    products = data.get("products", [])

    items = []
    total = 0
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        p = next((x for x in products if x["id"] == pid), None)
        if not p:
            continue
        price = get_opt_price(p, data)
        line = price * qty
        total += line
        items.append({
            "pid": pid,
            "sku": p["sku"],
            "name": p["name"],
            "qty": qty,
            "price_usd": price,
            "line_usd": line
        })

    try:
        db.table("bot_orders").insert({
            "dealer_id": str(chat_id),
            "dealer_name": dealer["name"] if dealer else "Noma'lum",
            "dealer_chat_id": chat_id,
            "items": items,
            "total_usd": total,
            "status": "new"
        }).execute()
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Xato: {e}")
        return

    carts[chat_id] = {}

    # Adminga xabar
    if ADMIN_CHAT_ID:
        try:
            items_text = "\n".join([f"• {i['sku']} ×{i['qty']} = {fmt_usd(i['line_usd'])}" for i in items])
            dealer_name = dealer['name'] if dealer else "Noma'lum"
            await ctx.bot.send_message(
                ADMIN_CHAT_ID,
                f"🆕 *Yangi zakaz!*\n"
                f"Diller: *{dealer_name}*\n\n"
                f"{items_text}\n\n"
                f"💰 Jami: *{fmt_usd(total)}*",
                parse_mode="Markdown"
            )
        except:
            pass

    await update.callback_query.edit_message_text(
        f"✅ *Zakazingiz qabul qilindi!*\n\n"
        f"📦 {len(items)} xil mahsulot\n"
        f"💰 Jami: *{fmt_usd(total)}*\n\n"
        f"Administrator tasdiqlagunicha kuting.",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# ADMIN BUYRUQLARI
# ═══════════════════════════════════════

async def approve_dealer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin dillerni tasdiqlash: /approve_CHATID"""
    text = update.message.text
    try:
        dealer_chat_id = int(text.split("_")[1])
        db.table("bot_dealers").update({"approved": True}).eq("chat_id", dealer_chat_id).execute()
        dealer = get_dealer(dealer_chat_id)
        await update.message.reply_text(f"✅ {dealer['name'] if dealer else dealer_chat_id} tasdiqlandi!")
        await ctx.bot.send_message(
            dealer_chat_id,
            "✅ *Siz tasdiqlandi!*\n\nEndi zakaz bera olasiz.\n/start buyrug'ini bosing.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}")


# ═══════════════════════════════════════
# ASOSIY
# ═══════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", handle_id))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"), approve_dealer))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
