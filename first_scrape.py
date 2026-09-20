import requests
from bs4 import BeautifulSoup

# یه سایت ساده برای تست
url = "https://example.com"

# درخواست به سایت
response = requests.get(url)

# چک کن موفق بود
print("Status Code:", response.status_code)

# پارس HTML
soup = BeautifulSoup(response.text, "html.parser")

# عنوان صفحه رو بگیر
title = soup.find("title")
print("Title:", title.text if title else "Not found")

# همه‌ی پاراگراف‌ها
paragraphs = soup.find_all("p")
for i, p in enumerate(paragraphs, 1):
    print(f"Paragraph {i}: {p.text}")