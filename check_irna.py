import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

url = "https://www.irna.ir"
print(f"🌐 در حال بررسی {url}...\n")

response = requests.get(url, headers=headers, timeout=15)
print(f"✅ Status Code: {response.status_code}\n")

soup = BeautifulSoup(response.text, "html.parser")
all_links = soup.find_all("a")
print(f"📊 Total links: {len(all_links)}\n")
print("=" * 60)

# ۳۰ لینک اول رو نشون بده (حتی کوتاه‌ها)
count = 0
for link in all_links:
    href = link.get("href", "")
    text = link.text.strip()
    
    if href:
        print(f"📌 متن: {text[:60] if text else '(خالی)'}")
        print(f"   🔗 {href}")
        print()
        count += 1
        if count >= 30:
            break