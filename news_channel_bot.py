import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

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

# ========== Logging ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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

# ========== پروکسی ==========
PROXY_URL = os.environ.get("PROXY_URL", "")

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=TOKEN, session=session)
    logger.info(f"🌐 استفاده از پروکسی: {PROXY_URL}")
else:
    bot = Bot(token=TOKEN)
    logger.info("🌐 بدون پروکسی (IP تمیز)")

dp = Dispatcher()

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
DB_FILE = "seen_news.db"


# ========== دیتابیس ==========

def init_db():
    """ساخت دیتابیس برای URLهای دیده‌شده"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_urls (
            url TEXT PRIMARY KEY,
            title TEXT,
            seen_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ دیتابیس آماده شد")


def is_url_seen(url):
    """چک کن آیا URL قبلاً دیده شده"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_urls WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_url_seen(url, title):
    """URL رو به عنوان دیده‌شده علامت بزن"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO seen_urls (url, title, seen_at) VALUES (?, ?, ?)",
        (url, title, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


# ========== توابع کمکی ==========

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


def is_recent(date_str, hours=48):
    """چک کن آیا خبر توی N ساعت اخیر منتشر شده"""
    if not date_str:
        return False
    
    try:
        try:
            dt = parsedate_to_datetime(date_str)
        except Exception:
            dt = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        return diff < timedelta(hours=hours)
    except Exception as e:
        logger.warning(f"⚠️ خطا در پارس تاریخ '{date_str}': {e}")
        return True


def translate_to_persian(text, max_retries=3):
    """ترجمه با Groq از طریق Render Proxy"""
    if not text or len(text.strip()) < 5:
        return ""
    
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
                logger.warning(f"   ⏳ خطای {response.status_code}، {wait_time} ثانیه صبر...")
                time.sleep(wait_time)
                continue
            else:
                return ""
        except Exception as e:
            logger.error(f"   ❌ خطا: {e}")
            time.sleep(5)
            continue
    return ""


def scrape_rss(source_name, rss_url):
    """استخراج اخبار از یه RSS (مرتب‌شده بر اساس تاریخ)"""
    logger.info(f"🌐 در حال دریافت از {source_name}...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            logger.warning(f"   ⚠️ هیچ خبری پیدا نشد")
            return []
        
        # ✅ مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
        entries = sorted(
            feed.entries,
            key=lambda x: x.get("published_parsed") or (0,),
            reverse=True
        )
        
        news_list = []
        
        for entry in entries[:15]:
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
        
        logger.info(f"   ✅ {len(news_list)} خبر از {source_name}")
        return news_list
    except Exception as e:
        logger.error(f"   ❌ خطا در {source_name}: {e}")
        return []


async def scrape_and_translate():
    """اسکرپ + فیلتر + چک تکراری + ترجمه + ذخیره در Excel"""
    logger.info("=" * 60)
    logger.info(f"🚀 شروع اسکرپ - {datetime.now()}")
    logger.info("=" * 60)
    
    init_db()
    
    all_news = []
    for source_name, rss_url in RSS_FEEDS.items():
        news = scrape_rss(source_name, rss_url)
        all_news.extend(news)
        await asyncio.sleep(0.3)
    
    logger.info(f"📊 مجموع: {len(all_news)} خبر استخراج شد")
    
    # فیلتر ۱: ایران-آمریکا
    filtered = [
        n for n in all_news 
        if is_iran_us_conflict(n["title_en"]) or is_iran_us_conflict(n["content_en"])
    ]
    logger.info(f"🔍 فیلتر (ایران-آمریکا): {len(filtered)} خبر")
    
    # فیلتر ۲: فقط خبرهای ۴۸ ساعت اخیر
    recent = [n for n in filtered if is_recent(n.get("date", ""), hours=48)]
    logger.info(f"🕐 خبرهای ۴۸ ساعت اخیر: {len(recent)} خبر")
    
    # فیلتر ۳: حذف تکراری‌ها
    new_news = [n for n in recent if not is_url_seen(n["url"])]
    logger.info(f"🆕 خبرهای جدید (نه تکراری): {len(new_news)} خبر")
    
    if not new_news:
        logger.info("⚠️ همه‌ی خبرها تکراری یا قدیمی هستن.")
        return 0
    
    # ترجمه
    logger.info(f"🌐 شروع ترجمه ({len(new_news)} خبر جدید)...")
    for i, news in enumerate(new_news, 1):
        logger.info(f"[{i}/{len(new_news)}] {news['title_en'][:60]}...")
        news["title_fa"] = await asyncio.to_thread(translate_to_persian, news["title_en"])
        await asyncio.sleep(1)
        
        if news["content_en"]:
            news["content_fa"] = await asyncio.to_thread(translate_to_persian, news["content_en"][:1000])
            await asyncio.sleep(1)
    
    # ذخیره در Excel
    df = pd.DataFrame(new_news)
    df.to_excel(EXCEL_FILE, index=False, engine="openpyxl")
    logger.info(f"✅ {len(new_news)} خبر جدید در '{EXCEL_FILE}' ذخیره شد!")
    
    # علامت‌گذاری
    for news in new_news:
        mark_url_seen(news["url"], news["title_en"])
    
    logger.info(f"✅ {len(new_news)} URL به دیتابیس اضافه شد")
    return len(new_news)


def load_news():
    """خوندن اخبار از Excel"""
    try:
        df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
        return df
    except Exception as e:
        logger.error(f"❌ خطا در خوندن Excel: {e}")
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
            logger.info(f"   ✅ خبر {i} ارسال شد")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"   ❌ خطا: {e}")


async def daily_job():
    """کار روزانه: اسکرپ + ترجمه + ارسال"""
    logger.info(f"⏰ اجرای کار روزانه - {datetime.now()}")
    
    count = await scrape_and_translate()
    
    if count == 0:
        logger.info("⚠️ خبر جدیدی نیست، ارسال انجام نمی‌شه.")
        return
    
    await send_news_to_channel()


# ========== دستورات ==========

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🤖 *ربات خبر KtMir*\n\n"
        "دستورات:\n"
        "📰 `/news` — ۵ خبر آخر\n"
        "📢 `/send` — ارسال به کانال\n"
        "🔄 `/update` — اسکرپ خبرهای جدید\n"
        "🧹 `/reset` — پاک کردن حافظه تکراری\n"
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
        "• `/update` — اسکرپ خبرهای جدید (۲-۳ دقیقه)\n"
        "• `/reset` — پاک کردن حافظه (برای تست)\n"
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
            logger.error(f"❌ خطا: {e}")


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
    
    await message.answer("🔄 در حال اسکرپ خبرهای جدید... (۲-۳ دقیقه)")
    count = await scrape_and_translate()
    
    if count > 0:
        await message.answer(f"✅ {count} خبر جدید پیدا شد!")
    else:
        await message.answer("⚠️ خبر جدیدی پیدا نشد (همه تکراری یا قدیمی بودن).")


@dp.message(Command("reset"))
async def reset_command(message: types.Message):
    if message.from_user.id != MY_USER_ID:
        await message.answer("❌ شما اجازه‌ی این کار رو ندارید.")
        return
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM seen_urls")
        conn.commit()
        conn.close()
        await message.answer("🧹 حافظه پاک شد. /update رو بزن.")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")


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
        logger.error(f"❌ خطا در Webhook: {e}")
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
        logger.info(f"✅ Webhook ست شد: {full_url}")
    
    init_db()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_job, "cron", hour=8, minute=0)
    scheduler.start()
    logger.info("⏰ زمان‌بندی: هر روز ساعت ۸:۰۰")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)