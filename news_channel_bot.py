import asyncio
import json
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import pandas as pd

# بارگذاری تنظیمات
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["telegram_token"]
CHANNEL_ID = int(config["channel_id"])

logging.basicConfig(level=logging.INFO)

# پروکسی سایفون
PROXY_URL = "http://127.0.0.1:8080"
session = AiohttpSession(proxy=PROXY_URL)

bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()


def load_news(file_path="iran_us_news_translated.xlsx"):
    """خوندن اخبار از Excel"""
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        return df
    except Exception as e:
        print(f"❌ خطا در خوندن Excel: {e}")
        return None


def format_news(news_row, index):
    """فرمت‌دهی یه خبر"""
    title_fa = news_row.get("title_fa", "")
    title_en = news_row.get("title_en", "بدون عنوان")
    url = news_row.get("url", "")
    source = news_row.get("source", "نامشخص")
    
    # اگه ترجمه فارسی خالی بود، از انگلیسی استفاده کن
    display_title = title_fa if title_fa and str(title_fa).strip() else title_en
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔗 متن کامل", url=url)]
        ]
    )
    
    message = (
        f"📰 *خبر {index}* — {source}\n\n"
        f"*{display_title}*\n"
    )
    
    return message, keyboard


async def send_daily_news():
    """ارسال اخبار روزانه به کانال"""
    print(f"\n⏰ ارسال اخبار - {datetime.now()}")
    
    df = load_news()
    if df is None or df.empty:
        await bot.send_message(CHANNEL_ID, "❌ هیچ خبری برای ارسال نیست.")
        return
    
    top_news = df.head(5)
    
    # پیام شروع
    await bot.send_message(
        CHANNEL_ID,
        f"🌅 *صبح بخیر!*\n\n"
        f"📰 *۵ خبر مهم امروز:*\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        parse_mode="Markdown"
    )
    await asyncio.sleep(2)
    
    # ارسال هر خبر
    for i, (_, row) in enumerate(top_news.iterrows(), 1):
        message, keyboard = format_news(row, i)
        try:
            await bot.send_message(
                CHANNEL_ID,
                message,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            print(f"   ✅ خبر {i} ارسال شد")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"   ❌ خطا در ارسال خبر {i}: {e}")


@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🤖 *ربات خبر KtMir*\n\n"
        "دستورات:\n"
        "📰 `/news` — ۵ خبر آخر\n"
        "📢 `/send` — ارسال به کانال\n"
        "ℹ️ `/help` — راهنما",
        parse_mode="Markdown"
    )


@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 *راهنما*\n\n"
        "این ربات هر روز صبح ساعت ۸، ۵ خبر مهم رو به کانال می‌فرسته.\n\n"
        "*دستورات:*\n"
        "• `/news` — ۵ خبر آخر\n"
        "• `/send` — ارسال فوری به کانال\n"
        "• `/start` — شروع",
        parse_mode="Markdown"
    )


@dp.message(Command("news"))
async def news_command(message: types.Message):
    await message.answer("⏳ در حال آماده‌سازی...")
    
    df = load_news()
    if df is None or df.empty:
        await message.answer("❌ هیچ خبری موجود نیست.")
        return
    
    top_news = df.head(5)
    
    for i, (_, row) in enumerate(top_news.iterrows(), 1):
        msg, keyboard = format_news(row, i)
        try:
            await message.answer(
                msg,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ خطا: {e}")


@dp.message(Command("send"))
async def send_command(message: types.Message):
    await message.answer("📢 در حال ارسال به کانال...")
    await send_daily_news()
    await message.answer("✅ ارسال شد!")


@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("❌ دستور نامشخص. از /help استفاده کن.")


async def main():
    print("🤖 News Channel Bot is running...")
    
    # زمان‌بندی: هر روز ساعت ۸ صبح
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_news, "cron", hour=8, minute=0)
    scheduler.start()
    
    print("⏰ زمان‌بندی: هر روز ساعت ۸:۰۰")
    print(f"📢 کانال: {CHANNEL_ID}")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())