import feedparser
import pandas as pd
from datetime import datetime
import time
import re
import json
import requests

# بارگذاری تنظیمات
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# آدرس Render Proxy (Groq)
RENDER_PROXY_URL = "https://ktmir-newsbot.onrender.com/groq"

# ========== RSS FEEDS ==========
RSS_FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Middle East": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "DW English": "https://rss.dw.com/rdf/rss-en-all",
    "France24": "https://www.france24.com/en/rss",
    "NYT World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
}

# ========== دسته‌بندی منابع ==========
SOURCE_CATEGORIES = {
    "BBC World": "عمومی",
    "BBC Middle East": "خاورمیانه",
    "Al Jazeera": "خاورمیانه",
    "DW English": "جهانی",
    "France24": "جهانی",
    "NYT World": "جهانی",
}

# ========== کلمات کلیدی ایران ==========
IRAN_KEYWORDS = [
    "Iran", "Iranian", "Tehran", "Khamenei", "IRGC",
    "Persian", "Ayatollah", "Hormuz", "Strait of Hormuz"
]

# ========== کلمات کلیدی آمریکا ==========
US_KEYWORDS = [
    "US", "USA", "United States", "America", "American",
    "Trump", "White House", "Washington",
    "Pentagon", "State Department"
]


def contains_word(text, word):
    """چک کن کلمه‌ی دقیق توی متن هست (نه بخشی از کلمه‌ی دیگه)"""
    if not text:
        return False
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def is_iran_us_conflict(text):
    """آیا خبر مربوط به درگیری ایران و آمریکاست؟"""
    if not text:
        return False
    has_iran = any(contains_word(text, kw) for kw in IRAN_KEYWORDS)
    has_us = any(contains_word(text, kw) for kw in US_KEYWORDS)
    return has_iran and has_us


def translate_to_persian(text, max_retries=3):
    """ترجمه با Groq از طریق Render Proxy"""
    if not text or len(text.strip()) < 5:
        return ""
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                RENDER_PROXY_URL,
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
                    print(f"   ⚠️ ساختار پاسخ عجیبه")
                    return ""
            
            elif response.status_code in [429, 500, 502, 503, 504]:
                wait_time = (attempt + 1) * 5
                print(f"   ⏳ خطای {response.status_code}، {wait_time} ثانیه صبر...")
                time.sleep(wait_time)
                continue
            
            else:
                print(f"   ❌ Error {response.status_code}")
                return ""
                
        except Exception as e:
            print(f"   ❌ خطا: {e}")
            time.sleep(5)
            continue
    
    print(f"   ❌ بعد از {max_retries} تلاش، ناموفق")
    return ""


def scrape_rss(source_name, rss_url):
    """استخراج اخبار از یه RSS"""
    print(f"\n🌐 در حال دریافت از {source_name}...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            print(f"   ⚠️ هیچ خبری پیدا نشد")
            return []
        
        news_list = []
        
        for entry in feed.entries[:15]:  # ← ۱۵ خبر از هر منبع
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            published = entry.get("published", "")
            summary = entry.get("summary", "")
            
            if title and url:
                news_list.append({
                    "source": source_name,
                    "category": SOURCE_CATEGORIES.get(source_name, "عمومی"),  # ← جدید
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


# ========== اجرا ==========

print("=" * 60)
print("🚀 شروع استخراج و ترجمه")
print("=" * 60)

all_news = []

for source_name, rss_url in RSS_FEEDS.items():
    news = scrape_rss(source_name, rss_url)
    all_news.extend(news)
    time.sleep(0.5)

print("\n" + "=" * 60)
print(f"📊 خلاصه: {len(all_news)} خبر از {len(set(n['source'] for n in all_news))} سایت")
print("=" * 60)

# فیلتر
print(f"\n🔍 فیلتر: فقط اخبار درگیری ایران و آمریکا...")
filtered_news = [
    n for n in all_news 
    if is_iran_us_conflict(n["title_en"]) or is_iran_us_conflict(n["content_en"])
]

print(f"✅ {len(filtered_news)} خبر مرتبط پیدا شد\n")

# نمایش دسته‌بندی‌ها
if filtered_news:
    print("📂 دسته‌بندی اخبار:")
    categories = {}
    for n in filtered_news:
        cat = n.get("category", "نامشخص")
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in categories.items():
        print(f"   • {cat}: {count} خبر")
    print()

# ترجمه همه‌ی خبرا
news_to_translate = filtered_news

print("=" * 60)
print(f"🌐 شروع ترجمه ({len(news_to_translate)} خبر)")
print("=" * 60)

for i, news in enumerate(news_to_translate, 1):
    print(f"\n[{i}/{len(news_to_translate)}] {news['title_en'][:70]}...")
    
    print("   🔄 ترجمه عنوان...")
    news["title_fa"] = translate_to_persian(news["title_en"])
    time.sleep(1)
    
    if news["content_en"]:
        print("   🔄 ترجمه متن...")
        news["content_fa"] = translate_to_persian(news["content_en"][:1000])
        time.sleep(1)
    
    print(f"   ✅ ترجمه شد: {news['title_fa'][:60]}...")

# ذخیره در Excel
if filtered_news:
    df = pd.DataFrame(filtered_news)
    output_file = "iran_us_news_translated.xlsx"
    df.to_excel(output_file, index=False, engine="openpyxl")
    print(f"\n✅ {len(filtered_news)} خبر در '{output_file}' ذخیره شد!")
    
    print("\n" + "=" * 60)
    print("📰 نمونه‌ی ترجمه:")
    print("=" * 60)
    for i, news in enumerate(news_to_translate[:5], 1):
        print(f"\n{i}. [{news.get('category', '?')}] 🇬🇧 {news['title_en']}")
        print(f"   🇮🇷 {news['title_fa']}")
else:
    print("\n⚠️ هیچ خبر مرتبطی پیدا نشد.")