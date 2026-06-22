"""
مساعد تيليغرام الشخصي — مدعوم بـ Claude
Personal Telegram Assistant powered by Claude (Anthropic)
"""

import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import anthropic

# ── إعداد السجل ──────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── التوكنات (من ملف .env أو متغيرات البيئة) ─────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]

# ── إعداد Claude ──────────────────────────────────────
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

SYSTEM_PROMPT = """أنت "نور"، مساعد شخصي ذكي يعمل عبر تطبيق تيليغرام.
أسلوبك: محترف، ودود، موجز.
لغتك الأساسية: العربية — وتجيب بنفس لغة المستخدم إن كتب بالإنجليزية.

وظائفك الرئيسية:
1. الإجابة على الأسئلة وتقديم المعلومات
2. إدارة المهام والتذكيرات
3. تلخيص النصوص والمستندات
4. صياغة الرسائل والمراسلات
5. توليد الأفكار ودعم القرارات

قواعد ثابتة:
- كن موجزاً ما لم يُطلب التفصيل
- استخدم الرموز التعبيرية باعتدال
- عند عدم التأكد من معلومة، قل ذلك صراحةً
- قدّم الخيارات حين يوجد أكثر من حل"""

# ── ذاكرة المحادثة (لكل مستخدم) ──────────────────────
# { user_id: [ {"role": "user"|"assistant", "content": "..."}, ... ] }
conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 20  # أقصى عدد رسائل في الذاكرة


def get_history(user_id: int) -> list[dict]:
    return conversations.setdefault(user_id, [])


def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    # احتفظ بآخر MAX_HISTORY رسالة فقط
    if len(history) > MAX_HISTORY:
        conversations[user_id] = history[-MAX_HISTORY:]


# ── الأوامر ───────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    await update.message.reply_text(
        f"مرحباً {name}! 👋\n"
        "أنا *نور*، مساعدك الشخصي الذكي.\n\n"
        "يمكنني مساعدتك في:\n"
        "• الإجابة على أسئلتك\n"
        "• تلخيص النصوص\n"
        "• صياغة الرسائل\n"
        "• توليد الأفكار والمقترحات\n\n"
        "فقط اكتب ما تريد! 💬\n"
        "أو اكتب /help لعرض الأوامر.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *الأوامر المتاحة:*\n\n"
        "/start — بدء المحادثة\n"
        "/help  — عرض هذه المساعدة\n"
        "/clear — مسح تاريخ المحادثة\n"
        "/summary — ملخص المحادثة الحالية\n\n"
        "وأي رسالة أخرى سأعالجها مباشرة! 🚀",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conversations.pop(uid, None)
    await update.message.reply_text("✅ تم مسح تاريخ المحادثة. نبدأ من جديد!")


async def cmd_summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    history = get_history(uid)
    if not history:
        await update.message.reply_text("لا توجد محادثة سابقة للتلخيص.")
        return

    await update.message.reply_text("⏳ أُعدّ الملخص...")
    history_text = "\n".join(
        f"{'المستخدم' if m['role']=='user' else 'نور'}: {m['content']}"
        for m in history
    )
    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system="لخّص المحادثة التالية في نقاط مختصرة باللغة العربية.",
        messages=[{"role": "user", "content": history_text}],
    )
    await update.message.reply_text(
        f"📝 *ملخص المحادثة:*\n\n{response.content[0].text}",
        parse_mode="Markdown",
    )


# ── معالج الرسائل الرئيسي ─────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    # أضف رسالة المستخدم للتاريخ
    add_to_history(uid, "user", text)

    # أظهر "يكتب..."
    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=get_history(uid),
        )
        reply = response.content[0].text

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        reply = "⚠️ حدث خطأ في الاتصال بالذكاء الاصطناعي. حاول مرة أخرى."

    # أضف رد المساعد للتاريخ
    add_to_history(uid, "assistant", reply)

    await update.message.reply_text(reply)


# ── معالج الأخطاء ────────────────────────────────────
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ: {ctx.error}", exc_info=ctx.error)


# ── تشغيل البوت ──────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("clear",   cmd_clear))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("✅ البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
