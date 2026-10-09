import logging
from decimal import Decimal, InvalidOperation
from html import escape
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from sqlalchemy import select
from app.config import settings
from app.database.session import SessionLocal, init_db
from app.database.models import User, Product, Category, Order, Deposit, LedgerEntry, SupportTicket
from app.services.shop import register_user, create_deposit, approve_deposit, reject_deposit, purchase_product, ShopError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kenova")

HOME = InlineKeyboardMarkup([
    [InlineKeyboardButton("🛍 Shop Products", callback_data="products"), InlineKeyboardButton("📂 Categories", callback_data="categories")],
    [InlineKeyboardButton("💰 My Balance", callback_data="balance"), InlineKeyboardButton("➕ Deposit", callback_data="deposit")],
    [InlineKeyboardButton("📦 My Orders", callback_data="orders"), InlineKeyboardButton("🧾 Transactions", callback_data="transactions")],
    [InlineKeyboardButton("👤 My Profile", callback_data="profile"), InlineKeyboardButton("🎧 Support", callback_data="support")],
    [InlineKeyboardButton("ℹ️ Terms & Privacy", callback_data="terms")],
])

def nav(back: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back), InlineKeyboardButton("🏠 Home", callback_data="home")]])

def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in settings.admin_ids)

async def safe_edit(query, text: str, keyboard=None):
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as exc:
        if "Message is not modified" not in str(exc):
            log.warning("Could not edit Telegram message: %s", type(exc).__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    if not tg:
        return
    with SessionLocal() as db:
        user = register_user(db, tg.id, tg.username, tg.first_name or "Customer")
        if user.is_blocked:
            await update.effective_message.reply_text("Your account is currently restricted. Contact support.")
            return
    await update.effective_message.reply_text(
        f"✨ <b>{escape(settings.shop_name)}</b>\n\nWelcome, {escape(tg.first_name or 'Customer')}!\nShop trusted digital services, track orders, and manage your wallet from one place.",
        parse_mode=ParseMode.HTML, reply_markup=HOME)

async def show_products(query, category_id: int | None = None):
    with SessionLocal() as db:
        stmt = select(Product).where(Product.active.is_(True)).order_by(Product.id.desc())
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        products = db.scalars(stmt.limit(30)).all()
        rows = [[InlineKeyboardButton(f"{p.name[:32]} — ৳{Decimal(p.price):.2f}", callback_data=f"product:{p.id}")] for p in products]
    rows.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    await safe_edit(query, "🛍 <b>Available Products</b>\nChoose a product below.", InlineKeyboardMarkup(rows))

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    tg = update.effective_user
    if not tg:
        return
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.telegram_id == tg.id))
        if user is None:
            user = register_user(db, tg.id, tg.username, tg.first_name or "Customer")
        if user.is_blocked:
            await safe_edit(query, "Your account is restricted. Please contact support.", nav())
            return
        if data == "home":
            await safe_edit(query, f"✨ <b>{escape(settings.shop_name)}</b>\nChoose an option below.", HOME)
        elif data == "products":
            await show_products(query)
        elif data == "categories":
            categories = db.scalars(select(Category).where(Category.active.is_(True)).order_by(Category.name)).all()
            rows = [[InlineKeyboardButton(c.name, callback_data=f"category:{c.id}")] for c in categories]
            rows.append([InlineKeyboardButton("🛍 All Products", callback_data="products")])
            rows.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
            await safe_edit(query, "📂 <b>Categories</b>", InlineKeyboardMarkup(rows))
        elif data.startswith("category:"):
            try: category_id = int(data.split(":", 1)[1])
            except ValueError:
                await safe_edit(query, "Invalid category.", nav("categories")); return
            await show_products(query, category_id)
        elif data.startswith("product:"):
            try: product_id = int(data.split(":", 1)[1])
            except ValueError:
                await safe_edit(query, "Invalid product.", nav("products")); return
            product = db.get(Product, product_id)
            if not product or not product.active:
                await safe_edit(query, "This product is no longer available.", nav("products")); return
            stock = "Unlimited" if product.stock is None else str(product.stock)
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Buy now", callback_data=f"buy:{product.id}")], [InlineKeyboardButton("⬅️ Products", callback_data="products"), InlineKeyboardButton("🏠 Home", callback_data="home")]])
            await safe_edit(query, f"🛍 <b>{escape(product.name)}</b>\n\n{escape(product.description or 'No description available.')}\n\n💵 Price: <b>৳{Decimal(product.price):.2f}</b>\n📦 Stock: {escape(stock)}", keyboard)
        elif data.startswith("buy:"):
            try: product_id = int(data.split(":", 1)[1])
            except ValueError:
                await safe_edit(query, "Invalid product.", nav("products")); return
            try:
                order = purchase_product(db, user.id, product_id)
                await safe_edit(query, f"✅ <b>Order placed!</b>\nOrder: <code>{escape(order.order_number)}</code>\nProduct: {escape(order.product_name)}\nTotal: ৳{Decimal(order.total):.2f}\nStatus: Pending fulfillment", nav())
            except ShopError as exc:
                await safe_edit(query, f"⚠️ {escape(str(exc))}", nav("products"))
        elif data == "balance":
            await safe_edit(query, f"💰 <b>Your balance</b>\n৳{Decimal(user.balance):.2f}", InlineKeyboardMarkup([[InlineKeyboardButton("➕ Deposit Funds", callback_data="deposit")], [InlineKeyboardButton("🏠 Home", callback_data="home")]]))
        elif data == "deposit":
            context.user_data["flow"] = "deposit_amount"
            await safe_edit(query, f"➕ <b>Deposit funds</b>\nMinimum deposit: ৳{settings.min_deposit}\n\nSend the amount as a number (example: 100).", nav())
            await query.message.reply_text("Please enter the deposit amount:")
        elif data == "orders":
            orders = db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc()).limit(10)).all()
            if not orders:
                text = "📦 You have no orders yet."
            else:
                text = "📦 <b>Your recent orders</b>\n\n" + "\n".join(f"<code>{escape(o.order_number)}</code> — {escape(o.product_name)} — ৳{Decimal(o.total):.2f} — {escape(o.status)}" for o in orders)
            await safe_edit(query, text, nav())
        elif data == "transactions":
            entries = db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.id.desc()).limit(10)).all()
            text = "🧾 <b>Recent transactions</b>\n\n" + ("\n".join(f"{escape(e.entry_type)}: {'+' if Decimal(e.amount) >= 0 else ''}৳{Decimal(e.amount):.2f} — <code>{escape(e.reference)}</code>" for e in entries) if entries else "No transactions yet.")
            await safe_edit(query, text, nav())
        elif data == "profile":
            await safe_edit(query, f"👤 <b>Your profile</b>\nName: {escape(user.first_name)}\nUsername: @{escape(user.username) if user.username else 'not set'}\nTelegram ID: <code>{user.telegram_id}</code>\nJoined: {user.joined_at.strftime('%Y-%m-%d') if user.joined_at else 'Unknown'}\nBalance: ৳{Decimal(user.balance):.2f}", nav())
        elif data == "support":
            await safe_edit(query, f"🎧 <b>Support</b>\nContact: {escape(settings.support_username)}\n\nYou can also send a message to this bot; support-ticket creation is available with /ticket your message.", nav())
        elif data == "terms":
            await safe_edit(query, "ℹ️ <b>Terms & Privacy</b>\nOnly purchase authorized products and services. Deposits remain pending until reviewed by an administrator. Refunds and fulfillment are subject to the shop's published policy. Do not send passwords or sensitive personal information in chat.", nav())
        elif data.startswith("depapprove:") or data.startswith("depreject:"):
            if not is_admin(update):
                await safe_edit(query, "⛔ Administrator access required.", nav()); return
            try: deposit_id = int(data.split(":", 1)[1])
            except ValueError:
                await safe_edit(query, "Invalid deposit ID.", nav()); return
            try:
                dep = approve_deposit(db, deposit_id, tg.id) if data.startswith("depapprove:") else reject_deposit(db, deposit_id, tg.id)
                await safe_edit(query, f"✅ Deposit {escape(dep.reference)} {escape(dep.status)}.", nav())
                customer = db.get(User, dep.user_id)
                if customer:
                    try: await context.bot.send_message(customer.telegram_id, f"Your deposit {dep.reference} has been {dep.status}.")
                    except Exception: log.info("Could not notify user %s", customer.telegram_id)
            except ShopError as exc:
                await safe_edit(query, f"⚠️ {escape(str(exc))}", nav())
        elif data == "admin_deposits":
            if not is_admin(update):
                await safe_edit(query, "⛔ Administrator access required.", nav()); return
            deposits = db.scalars(select(Deposit).where(Deposit.status == "pending").order_by(Deposit.id).limit(15)).all()
            rows = [[InlineKeyboardButton(f"{d.reference} · ৳{Decimal(d.amount):.2f}", callback_data=f"depview:{d.id}")] for d in deposits]
            rows.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
            await safe_edit(query, "🛡 <b>Pending deposits</b>", InlineKeyboardMarkup(rows))
        elif data.startswith("depview:"):
            if not is_admin(update):
                await safe_edit(query, "⛔ Administrator access required.", nav()); return
            try: dep = db.get(Deposit, int(data.split(":", 1)[1]))
            except ValueError: dep = None
            if not dep:
                await safe_edit(query, "Deposit not found.", nav("admin_deposits")); return
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"depapprove:{dep.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"depreject:{dep.id}")], [InlineKeyboardButton("⬅️ Back", callback_data="admin_deposits")]])
            await safe_edit(query, f"🧾 <b>Deposit review</b>\nRef: <code>{escape(dep.reference)}</code>\nCustomer DB ID: {dep.user_id}\nAmount: ৳{Decimal(dep.amount):.2f}\nMethod: {escape(dep.method)}\nPayment ref: <code>{escape(dep.payment_reference)}</code>\nStatus: {escape(dep.status)}", kb)
        else:
            await safe_edit(query, "This button is not recognized. Please return Home.", nav())

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    message = update.effective_message
    if not tg or not message or not message.text:
        return
    flow = context.user_data.get("flow")
    if flow == "deposit_amount":
        try:
            amount = Decimal(message.text.strip())
            if amount != amount.quantize(Decimal("0.01")) or amount < settings.min_deposit or amount > Decimal("1000000"):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            await message.reply_text(f"Enter a valid amount between ৳{settings.min_deposit} and ৳1,000,000.")
            return
        context.user_data["deposit_amount"] = str(amount)
        context.user_data["flow"] = "deposit_method"
        await message.reply_text("Choose payment method:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 bKash", callback_data="paymethod:bKash"), InlineKeyboardButton("🟠 Nagad", callback_data="paymethod:Nagad")],
            [InlineKeyboardButton("🔵 Rocket", callback_data="paymethod:Rocket")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ]))
    elif flow == "deposit_reference":
        amount = Decimal(context.user_data.get("deposit_amount", "0"))
        method = context.user_data.get("deposit_method", "")
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_id == tg.id))
            if not user:
                user = register_user(db, tg.id, tg.username, tg.first_name or "Customer")
            try:
                dep = create_deposit(db, user, amount, method, message.text)
            except ShopError as exc:
                await message.reply_text(str(exc)); return
        context.user_data.clear()
        await message.reply_text(f"✅ Deposit request submitted.\nReference: {dep.reference}\nAmount: ৳{amount:.2f}\nStatus: Pending review. Funds are not added until an admin verifies the payment.", reply_markup=HOME)
        for admin_id in settings.admin_ids:
            try:
                await context.bot.send_message(admin_id, f"New deposit request\nRef: {dep.reference}\nCustomer Telegram ID: {tg.id}\nAmount: ৳{amount:.2f}\nMethod: {method}\nPayment reference: {message.text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Review deposits", callback_data="admin_deposits")]]))
            except Exception: log.info("Could not notify admin %s", admin_id)
    elif message.text.startswith("/ticket "):
        body = message.text[8:].strip()
        if not body or len(body) > 2000:
            await message.reply_text("Usage: /ticket Describe your issue (max 2000 characters).", reply_markup=HOME); return
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_id == tg.id))
            if not user: user = register_user(db, tg.id, tg.username, tg.first_name or "Customer")
            ticket = SupportTicket(user_id=user.id, message=body)
            db.add(ticket); db.commit()
            ticket_id = ticket.id
        await message.reply_text(f"🎧 Support ticket #{ticket_id} created. We will review it.", reply_markup=HOME)
    else:
        await message.reply_text("Use the menu buttons below, or /start to open the main menu.", reply_markup=HOME)

async def payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = (query.data or "").split(":", 1)[-1]
    if method not in {"bKash", "Nagad", "Rocket"} or context.user_data.get("flow") != "deposit_method":
        await safe_edit(query, "This deposit session expired. Start again from Deposit.", nav()); return
    number = {"bKash": settings.bkash_number, "Nagad": settings.nagad_number, "Rocket": settings.rocket_number}[method]
    context.user_data["deposit_method"] = method
    context.user_data["flow"] = "deposit_reference"
    instructions = f"Send payment to: <code>{escape(number)}</code>" if number else "Payment destination has not been configured yet. Contact support before paying."
    await safe_edit(query, f"💳 <b>{escape(method)} deposit</b>\nAmount: ৳{Decimal(context.user_data.get('deposit_amount', '0')):.2f}\n{instructions}\n\nAfter paying, send the transaction reference here. Your balance will remain unchanged until an admin verifies the payment.", nav())

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Administrator access required."); return
    await update.effective_message.reply_text("🛡 KENOVA Admin\nUse the buttons to review pending deposits.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🧾 Pending deposits", callback_data="admin_deposits")]]))

async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with SessionLocal() as db:
        products = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.id.desc()).limit(30)).all()
        rows = [[InlineKeyboardButton(f"{p.name[:32]} — ৳{Decimal(p.price):.2f}", callback_data=f"product:{p.id}")] for p in products]
    rows.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    await update.effective_message.reply_text("🛍 <b>Available products</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    log.error("Unhandled bot error: %s", type(error).__name__ if error else "UnknownError")
    if isinstance(update, Update) and update.effective_message:
        try: await update.effective_message.reply_text("Something went wrong. Please try again or contact support.")
        except Exception: pass

def main():
    settings.validate()
    init_db()
    app = Application.builder().token(settings.bot_token).connect_timeout(20).read_timeout(30).write_timeout(20).pool_timeout(20).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(payment_method, pattern=r"^paymethod:"))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.COMMAND, on_text))
    app.add_error_handler(error_handler)
    log.info("KENOVA SHOP bot starting. Database configured; secrets are not logged.")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
