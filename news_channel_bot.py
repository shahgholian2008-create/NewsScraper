import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import pandas as pd
import feedparser
import requests
import uvicorn

# ========== بارگذاری تنظیمات ==========
if os.path.exists("config.json"):
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    TOKEN = config["telegram_token"]
    CHANNEL_ID = int(config["channel_id"])
    MY_USER_ID = int(config["my_user_id"])
else:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    MY_USER_ID = int(os.environ.get("MY_USER_ID", 0))

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not found!")

logging.basicConfig(level=logging.INFO)

# ========== پروکسی (فقط لوکال) ==========
PROXY_URL = os.environ.get("PROXY_URL", "")

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=TOKEN, session=session)
    print(f"🌐 استفاده از پروکسی: {PROXY_URL}")
else:
    bot = Bot(token=TOKEN)
    print("🌐 بدون پروکسی (IP تمیز)")

dp = Dispatcher()

# Webhook URL
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_PATH = "/webhook"

app = FastAPI()

# ========== RSS FEEDS ==========
RSS_FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Middle East": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "DW English": "https://rss.dw.com/rdf/rss-en-all",
    "France24": "https://www.france24.com/en/rss",
    "NYT World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
}

SOURCE_CATEGORIES = {
    "BBC World": "عمومی",
    "BBC Middle East": "خاورمیانه",
    "Al Jazeera": "خاورمیانه",
    "DW English": "جهانی",
    "France24": "جهانی",
    "NYT World": "جهانی",
}

IRAN_KEYWORDS = [
    "Iran", "Iranian", "Tehran", "Khamenei", "IRGC",
    "Persian", "Ayatollah", "Hormuz", "Strait of Hormuz"
]

US_KEYWORDS = [
    "US", "USA", "United States", "America", "American",
    "Trump", "White House", "Washington",
    "Pentagon", "State Department"
]

EXCEL_FILE = "iran_us_news_translated.xlsx"


# ========== توابع ==========

def contains_word(text, word):
    if not text:
        return False
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def is_iran_us_conflict(text):
    if not text:
        return False
    has_iran = any(contains_word(text, kw) for kw in IRAN_KEYWORDS)
    has_us = any(contains_word(text, kw) for kw in US_KEYWORDS)
    return has_iran and has_us


def translate_to_persian(text, max_retries=3):
    """ترجمه با Groq از طریق Render Proxy"""
    if not text or len(text.strip()) < 5:
        return ""
    
    # آدرس Groq Proxy روی Render
    groq_url = "https://ktmir-newsbot.onrender.com/groq"
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                groq_url,
                json={
                    "model": "openai/gpt-oss-120b",
                    "prompt": f"""Translate the following English news text to Persian (Farsi).
Keep it natural and journalistic. Do NOT add any explanation, just the translation.

Text:
{text[:2000]}"""
                },
                timeout=90
            )
            
            if response.status_code == 200:
                result = response.json()
                try:
                    return result["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError):
                    return ""
            elif response.status_code in [429, 500, 502, 503, 504]:
                wait_time = (attempt + 1) * 5
                print(f"   ⏳ خطای {response.status_code}، {wait_time} ثانیه صبر...")
                time.sleep(wait_time)
                continue
            else:
                return ""
        except Exception as e:
            print(f"   ❌ خطا: {e}")
            time.sleep(5)
            continue
    return ""


def scrape_rss(source_name, rss_url):
    """استخراج اخبار از یه RSS"""
    print(f"\n🌐 در حال دریافت از {source_name}...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            return []
        
        news_list = []
        
        for entry in feed.entries[:15]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            published = entry.get("published", "")
            summary = entry.get("summary", "")
            
            if title and url:
                news_list.append({
                    "source": source_name,
                    "category": SOURCE_CATEGORIES.get(source_name, "عمومی"),
                    "title_en": title,
                    "url": url,
                    "date": published if published else datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "content_en": summary.strip() if summary else "",
                    "title_fa": "",
                    "content_fa": ""
                })
        
        print(f"   ✅ {len(news_list)} خبر از {source_name}")
        return news_list
    except Exception as e:
        print(f"   ❌ خطا در {source_name}: {e}")
        return []


async def scrape_and_translate():
    """اسکرپ + فیلتر + ترجمه + ذخیره در Excel"""
    print("\n" + "=" * 60)
    print(f"🚀 شروع اسکرپ - {datetime.now()}")
    print("=" * 60)
    
    all_news = []
    for source_name, rss_url in RSS_FEEDS.items():
        news = scrape_rss(source_name, rss_url)
        all_news.extend(news)
        await asyncio.sleep(0.5)
    
    print(f"\n📊 مجموع: {len(all_news)} خبر")
    
    # فیلتر
    filtered_news = [
        n for n in all_news 
        if is_iran_us_conflict(n["title_en"]) or is_iran_us_conflict(n["content_en"])
    ]
    print(f"🔍 فیلتر: {len(filtered_news)} خبر مرتبط")
    
    if not filtered_news:
        return False
    
    # ترجمه
    print(f"\n🌐 شروع ترجمه ({len(filtered_news)} خبر)...")
    for i, news in enumerate(filtered_news, 1):
        print(f"\n[{i}/{len(filtered_news)}] {news['title_en'][:60]}...")
        news["title_fa"] = await asyncio.to_thread(translate_to_persian, news["title_en"])
        await asyncio.sleep(1)
        
        if news["content_en"]:
            news["content_fa"] = await asyncio.to_thread(translate_to_persian, news["content_en"][:1000])
            await asyncio.sleep(1)
    
    # ذخیره در Excel
    df = pd.DataFrame(filtered_news)
    df.to_excel(EXCEL_FILE, index=False, engine="openpyxl")
    print(f"\n✅ {len(filtered_news)} خبر در '{EXCEL_FILE}' ذخیره شد!")
    
    return True


def load_news():
    """خوندن اخبار از Excel"""
    try:
        df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
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
    
    display_title = title_fa if title_fa and str(title_fa).strip() else title_en
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔗 متن کامل", url=url)]
        ]
    )
    
    message = f"📰 *خبر {index}* — {source}\n\n*{display_title}*\n"
    return message, keyboard


async def send_news_to_channel():
    """ارسال اخبار به کانال"""
    df = load_news()
    if df is None or df.empty:
        await bot.send_message(CHANNEL_ID, "❌ هیچ خبری برای ارسال نیست.")
        return
    
    top_news = df.head(5)
    
    await bot.send_message(
        CHANNEL_ID,
        f"🌅 *صبح بخیر!*\n\n"
        f"📰 *۵ خبر مهم امروز:*\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        parse_mode="Markdown"
    )
    await asyncio.sleep(2)
    
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
            print(f"   ❌ خطا: {e}")


async def daily_job():
    """کار روزانه: اسکرپ + ترجمه + ارسال"""
    print(f"\n⏰ اجرای کار روزانه - {datetime.now()}")
    
    # ۱. اسکرپ + ترجمه
    success = await scrape_and_translate()
    
    if not success:
        await bot.send_message(CHANNEL_ID, "❌ هیچ خبری پیدا نشد.")
        return
    
    # ۲. ارسال به کانال
    await send_news_to_channel()


# ========== دستورات ربات ==========

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🤖 *ربات خبر KtMir*\n\n"
        "دستورات:\n"
        "📰 `/news` — ۵ خبر آخر\n"
        "📢 `/send` — ارسال به کانال\n"
        "🔄 `/update` — اسکرپ و ترجمه جدید\n"
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
        "• `/update` — اسکرپ و ترجمه جدید (۲-۳ دقیقه)\n"
        "• `/start` — شروع",
        parse_mode="Markdown"
    )


@dp.message(Command("news"))
async def news_command(message: types.Message):
    if message.from_user.id != MY_USER_ID:
        await message.answer("❌ شما اجازه‌ی این کار رو ندارید.")
        return
    
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
    if message.from_user.id != MY_USER_ID:
        await message.answer("❌ شما اجازه‌ی این کار رو ندارید.")
        return
    
    await message.answer("📢 در حال ارسال به کانال...")
    await send_news_to_channel()
    await message.answer("✅ ارسال شد!")


@dp.message(Command("update"))
async def update_command(message: types.Message):
    if message.from_user.id != MY_USER_ID:
        await message.answer("❌ شما اجازه‌ی این کار رو ندارید.")
        return
    
    await message.answer("🔄 در حال اسکرپ و ترجمه... (۲-۳ دقیقه)")
    success = await scrape_and_translate()
    
    if success:
        await message.answer("✅ اخبار به‌روزرسانی شد!")
    else:
        await message.answer("❌ هیچ خبری پیدا نشد.")


@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("❌ دستور نامشخص. از /help استفاده کن.")


# ========== Webhook ==========

@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"❌ خطا در Webhook: {e}")
    return {"ok": True}


@app.get("/")
async def health():
    return {"status": "running"}


# ========== Startup ==========

@app.on_event("startup")
async def startup():
    if WEBHOOK_URL:
        full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(full_url)
        print(f"✅ Webhook ست شد: {full_url}")
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_job, "cron", hour=8, minute=0)
    scheduler.start()
    print("⏰ زمان‌بندی: هر روز ساعت ۸:۰۰")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)