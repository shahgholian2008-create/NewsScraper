# 📰 NewsScraper — ربات خبری هوشمند

پروژه‌ای برای استخراج، فیلتر و ترجمه‌ی اخبار از منابع معتبر بین‌المللی.

## ✨ قابلیت‌ها

- 📡 استخراج از ۳ منبع معتبر (BBC World, BBC Middle East, Al Jazeera)
- 🔍 فیلتر دقیق (فقط اخبار درگیری ایران و آمریکا)
- 🌐 ترجمه‌ی خودکار به فارسی (با Groq API)
- 📊 ذخیره در Excel (دو زبانه)
- 🔒 دور زدن تحریم با Render Proxy

## 🛠 تکنولوژی‌ها

- Python 3.x
- feedparser (RSS)
- pandas, openpyxl (Excel)
- requests (HTTP)
- Groq API (ترجمه)
- Render Proxy (دور زدن تحریم)

## 📁 ساختار پروژه

NewsScraper/
├── english_news_scraper.py       # فایل اصلی
├── config.json                   # تنظیمات (در .gitignore)
├── requirements.txt
├── README.md
├── .gitignore
└── iran_us_news_translated.xlsx  # خروجی

## 🚀 نصب و اجرا

### ۱. نصب کتابخانه‌ها
pip install feedparser pandas openpyxl requests

### ۲. ساخت فایل config.json
{
  "gemini_api_key": "YOUR_KEY",
  "groq_api_key": "YOUR_KEY"
}

### ۳. اجرا
python english_news_scraper.py

## 🌐 معماری

RSS (BBC, Al Jazeera) → کامپیوتر تو (ایران) → Render Proxy (IP تمیز) → Groq API → Excel

## 📝 مجوز

این پروژه برای اهداف آموزشی و شخصی توسعه یافته است.