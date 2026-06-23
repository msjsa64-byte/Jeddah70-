"""
مساعد تيليغرام الشخصي — مدعوم بـ Gemini (مجاني)
"""

import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

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

# ذاكرة المحادثة
conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 20


def get_history(user_id: int) -> list[dict]:
    return conversations.setdefault(user_id, [])


def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "parts": [content]})
    if len(history) > MAX_HISTORY:
        conversations[user_id] = history[-MAX_HISTORY:]


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
        "فقط اكتب ما تريد! 💬",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *الأوامر المتاحة:*\n\n"
        "/start — بدء المحادثة\n"
        "/help  — عرض هذه المساعدة\n"
        "/clear — مسح تاريخ المحادثة\n\n"
        "وأي رسالة أخرى سأعالجها مباشرة! 🚀",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conversations.pop(uid, None)
    await update.message.reply_text("✅ تم مسح تاريخ المحادثة. نبدأ من جديد!")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    add_to_history(uid, "user", text)

    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )
        chat = model.start_chat(history=get_history(uid)[:-1])
        response = chat.send_message(text)
        reply = response.text

    except Exception as e:
        logger.error(f"Gemini error: {e}")
        reply = "⚠️ حدث خطأ مؤقت. حاول مرة أخرى."

    add_to_history(uid, "model", reply)
    await update.message.reply_text(reply)


async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ: {ctx.error}", exc_info=ctx.error)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    logger.info("✅ البوت يعمل مع Gemini...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
