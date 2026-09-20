import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_full_content(url):
    """استخراج متن کامل از یه خبر"""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        
        content_parts = []
        for p in paragraphs:
            text_p = p.text.strip()
            if len(text_p) > 40:
                content_parts.append(text_p)
        
        return "\n\n".join(content_parts)
    except Exception:
        return ""


def scrape_bbc_persian():
    """استخراج از BBC Persian"""
    print("\n🌐 در حال دریافت از BBC Persian...")
    url = "https://www.bbc.com/persian"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        all_links = soup.find_all("a")
        
        news_list = []
        seen_urls = set()
        
        for link in all_links:
            href = link.get("href", "")
            text = link.text.strip()
            
            if text and len(text) > 30 and href:
                if href.startswith("/"):
                    href = "https://www.bbc.com" + href
                
                if "bbc.com/persian/articles/" in href and href not in seen_urls:
                    seen_urls.add(href)
                    news_list.append({
                        "source": "BBC Persian",
                        "title": text,
                        "url": href,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "content": ""
                    })
            
            if len(news_list) >= 5:
                break
        
        print(f"   ✅ {len(news_list)} خبر از BBC")
        
        # استخراج متن کامل
        for i, news in enumerate(news_list, 1):
            print(f"      [{i}/{len(news_list)}] در حال استخراج متن کامل...")
            news["content"] = get_full_content(news["url"])
            time.sleep(0.5)
        
        return news_list
        
    except Exception as e:
        print(f"   ❌ خطا در BBC: {e}")
        return []


def scrape_tabnak():
    """استخراج از Tabnak"""
    print("\n🌐 در حال دریافت از Tabnak...")
    url = "https://www.tabnak.ir"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        all_links = soup.find_all("a")
        
        news_list = []
        seen_urls = set()
        
        for link in all_links:
            href = link.get("href", "")
            text = link.text.strip()
            
            if text and len(text) > 30 and href:
                if href.startswith("/"):
                    href = "https://www.tabnak.ir" + href
                
                if "tabnak.ir/" in href and href not in seen_urls and "/news/" in href:
                    seen_urls.add(href)
                    news_list.append({
                        "source": "Tabnak",
                        "title": text,
                        "url": href,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "content": ""
                    })
            
            if len(news_list) >= 5:
                break
        
        print(f"   ✅ {len(news_list)} خبر از Tabnak")
        
        # استخراج متن کامل
        for i, news in enumerate(news_list, 1):
            print(f"      [{i}/{len(news_list)}] در حال استخراج متن کامل...")
            news["content"] = get_full_content(news["url"])
            time.sleep(0.5)
        
        return news_list
        
    except Exception as e:
        print(f"   ❌ خطا در Tabnak: {e}")
        return []


# ========== اجرا ==========

print("=" * 60)
print("🚀 شروع استخراج از چند سایت")
print("=" * 60)

all_news = []
all_news.extend(scrape_bbc_persian())
all_news.extend(scrape_tabnak())

print("\n" + "=" * 60)
print(f"📊 خلاصه: {len(all_news)} خبر از {len(set(n['source'] for n in all_news))} سایت")
print("=" * 60)

# ذخیره در Excel
if all_news:
    df = pd.DataFrame(all_news)
    output_file = "multi_news_full.xlsx"
    df.to_excel(output_file, index=False, engine="openpyxl")
    print(f"\n✅ {len(all_news)} خبر در '{output_file}' ذخیره شد!")
else:
    print("\n❌ هیچ خبری استخراج نشد!")