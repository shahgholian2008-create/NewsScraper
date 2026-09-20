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
MY_CHAT_ID = int(config["my_chat_id"])

logging.basicConfig(level=logging.INFO)

# پروکسی سایفون
PROXY_URL = "http://127.0.0.1:8080"
session = AiohttpSession(proxy=PROXY_URL)

bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()


def load_news(file_path="multi_news_full.xlsx"):
    """خوندن اخبار از فایل Excel"""
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        return df
    except Exception as e:
        print(f"❌ خطا در خوندن Excel: {e}")
        return None


def format_news_message(news_row, index):
    """فرمت‌دهی یه خبر برای ارسال"""
    title = news_row.get("title", "بدون عنوان")
    url = news_row.get("url", "")
    source = news_row.get("source", "نامشخص")
    
    message = (
        f"📰 *خبر {index}* — {source}\n\n"
        f"*{title}*\n\n"
        f"🔗 [متن کامل]({url})"
    )
    return message


async def send_daily_news():
    """ارسال اخبار روزانه"""
    print(f"⏰ ارسال اخبار روزانه - {datetime.now()}")
    
    df = load_news()
    if df is None or df.empty:
        await bot.send_message(MY_CHAT_ID, "❌ هیچ خبری برای ارسال نیست.")
        return
    
    top_news = df.head(5)
    
    await bot.send_message(
        MY_CHAT_ID,
        f"🌅 *صبح بخیر!*\n\n"
        f"📰 *۵ خبر مهم امروز:*\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    for i, (_, row) in enumerate(top_news.iterrows(), 1):
        message = format_news_message(row, i)
        try:
            await bot.send_message(MY_CHAT_ID, message, disable_web_page_preview=True)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ خطا در ارسال خبر {i}: {e}")


# ========== دستورات ربات ==========

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🤖 *ربات خبر KtMir*\n\n"
        "دستورات:\n"
        "📰 `/news` — دریافت ۵ خبر آخر\n"
        "🔄 `/refresh` — به‌روزرسانی اخبار\n"
        "ℹ️ `/help` — راهنما"
    )


@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 *راهنما*\n\n"
        "این ربات هر روز صبح ساعت ۸، ۵ خبر مهم رو برات می‌فرسته.\n\n"
        "*دستورات:*\n"
        "• `/news` — ۵ خبر آخر\n"
        "• `/refresh` — به‌روزرسانی\n"
        "• `/start` — شروع"
    )


@dp.message(Command("news"))
async def news_command(message: types.Message):
    await message.answer("⏳ در حال آماده‌سازی اخبار...")
    
    df = load_news()
    if df is None or df.empty:
        await message.answer("❌ هیچ خبری موجود نیست.")
        return
    
    top_news = df.head(5)
    
    await message.answer(
        f"📰 *۵ خبر آخر:*\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    for i, (_, row) in enumerate(top_news.iterrows(), 1):
        msg = format_news_message(row, i)
        try:
            await message.answer(msg, disable_web_page_preview=True)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ خطا در ارسال خبر {i}: {e}")


@dp.message(Command("refresh"))
async def refresh_command(message: types.Message):
    await message.answer("🔄 در حال به‌روزرسانی اخبار...")
    
    import subprocess
    try:
        result = subprocess.run(
            ["python", "multi_scraper.py"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            await message.answer("✅ اخبار به‌روزرسانی شد!")
        else:
            await message.answer(f"❌ خطا:\n{result.stderr[:500]}")
    except Exception as e:
        await message.answer(f"❌ خطا: {str(e)}")


@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("❌ دستور نامشخص. از /help استفاده کن.")


# ========== اجرا ==========

async def main():
    print("🤖 News Bot is running...")
    
    # زمان‌بندی: هر روز ساعت ۸ صبح
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_news, "cron", hour=8, minute=0)
    scheduler.start()
    
    print("⏰ زمان‌بندی فعال شد: هر روز ساعت ۸:۰۰")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())