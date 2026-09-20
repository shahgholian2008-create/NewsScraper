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

# آدرس Render Proxy
RENDER_PROXY_URL = "https://ktmir-newsbot.onrender.com/groq"

RSS_FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Middle East": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
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


def translate_to_persian(text):
    """ترجمه با Groq از طریق Render Proxy"""
    if not text or len(text.strip()) < 5:
        return ""
    
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
                print(f"   ⚠️ ساختار پاسخ: {result}")
                return ""
        else:
            print(f"   ❌ Error {response.status_code}: {response.text[:200]}")
            return ""
            
    except Exception as e:
        print(f"   ❌ خطا: {e}")
        return ""

def scrape_rss(source_name, rss_url):
    print(f"\n🌐 در حال دریافت از {source_name}...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            print(f"   ⚠️ هیچ خبری پیدا نشد")
            return []
        
        news_list = []
        
        for entry in feed.entries[:30]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            published = entry.get("published", "")
            summary = entry.get("summary", "")
            
            if title and url:
                news_list.append({
                    "source": source_name,
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

# ترجمه همه‌ی خبرا
news_to_translate = filtered_news

print("=" * 60)
print(f"🌐 شروع ترجمه ({len(news_to_translate)} خبر)")
print("=" * 60)

for i, news in enumerate(news_to_translate, 1):
    print(f"\n[{i}/{len(news_to_translate)}] {news['title_en'][:70]}...")
    
    print("   🔄 ترجمه عنوان...")
    news["title_fa"] = translate_to_persian(news["title_en"])
    time.sleep(10)
    
    if news["content_en"]:
        print("   🔄 ترجمه متن...")
        news["content_fa"] = translate_to_persian(news["content_en"][:1000])
        time.sleep(10)
    
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
    for i, news in enumerate(news_to_translate, 1):
        print(f"\n{i}. 🇬🇧 {news['title_en']}")
        print(f"   🇮🇷 {news['title_fa']}")
else:
    print("\n⚠️ هیچ خبر مرتبطی پیدا نشد.")