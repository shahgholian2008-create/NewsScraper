import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

# آدرس سایت
url = "https://www.bbc.com/persian"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("⏳ در حال دریافت اخبار از BBC Persian...")

response = requests.get(url, headers=headers)
print(f"✅ Status Code: {response.status_code}")

soup = BeautifulSoup(response.text, "html.parser")
all_links = soup.find_all("a")
print(f"📊 Total links found: {len(all_links)}")
print("-" * 50)

# لیست برای ذخیره‌ی اخبار
news_list = []
seen_urls = set()

for link in all_links:
    href = link.get("href", "")
    text = link.text.strip()
    
    # فیلتر
    if text and len(text) > 30 and href:
        if href.startswith("/"):
            href = "https://www.bbc.com" + href
        
        # فقط لینک‌های article (نه live)
        if "bbc.com/persian/articles/" in href and href not in seen_urls:
            seen_urls.add(href)
            news_list.append({
                "title": text,
                "url": href,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    
    if len(news_list) >= 10:  # فقط ۱۰ خبر برای تست
        break

print(f"\n📰 {len(news_list)} خبر پیدا شد. حالا متن کامل رو می‌گیریم...\n")

# ⭐ حالا برای هر خبر، متن کامل رو بگیر
for i, news in enumerate(news_list, 1):
    try:
        print(f"[{i}/{len(news_list)}] {news['title'][:60]}...")
        
        # درخواست به صفحه‌ی خبر
        article_response = requests.get(news["url"], headers=headers, timeout=10)
        article_soup = BeautifulSoup(article_response.text, "html.parser")
        
        # استخراج پاراگراف‌های متن خبر
        paragraphs = article_soup.find_all("p")
        
        # جمع‌آوری متن
        content_parts = []
        for p in paragraphs:
            text_p = p.text.strip()
            if len(text_p) > 40:  # فقط پاراگراف‌های بلند
                content_parts.append(text_p)
        
        news["content"] = "\n\n".join(content_parts)
        
        # مکث کوتاه (برای اینکه به سرور فشار نیاریم)
        time.sleep(0.5)
        
    except Exception as e:
        print(f"   ❌ خطا: {e}")
        news["content"] = ""

# ذخیره در Excel
df = pd.DataFrame(news_list)
output_file = "bbc_news_full.xlsx"
df.to_excel(output_file, index=False, engine="openpyxl")

print(f"\n✅ {len(news_list)} خبر با متن کامل در '{output_file}' ذخیره شد!")