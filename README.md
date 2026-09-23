# 📰 NewsScraper — ربات خبری هوشمند

پروژه‌ای برای استخراج، فیلتر، ترجمه و ارسال خودکار اخبار از منابع معتبر بین‌المللی.

---

## ✨ قابلیت‌ها

| قابلیت | توضیح |
|--------|-------|
| 📡 ۶ منبع RSS | BBC World, BBC Middle East, Al Jazeera, DW, France24, NYT |
| 🔍 فیلتر هوشمند | ایران-آمریکا + نفت + طلا |
| 🕐 فیلتر تاریخ | فقط اخبار ۴۸ ساعت اخیر |
| 🆕 جلوگیری از تکراری | دیتابیس SQLite |
| 🌐 ترجمه با Groq | ترجمه‌ی عنوان به فارسی |
| 📱 ربات تلگرام | با Webhook |
| ⏰ زمان‌بندی | هر ۲ ساعت خودکار |
| 🔒 دور زدن تحریم | Render Proxy |

---

## 🛠 تکنولوژی‌ها

- Python 3.10+
- feedparser — خواندن RSS
- aiogram 3.x — ربات تلگرام
- FastAPI — وب‌سرور Webhook
- APScheduler — زمان‌بندی
- Groq API — ترجمه
- SQLite — دیتابیس
- Render — هاست

---

## 📁 ساختار پروژه

NewsScraper/
├── news_channel_bot.py          # فایل اصلی
├── english_news_scraper.py      # اسکرپر مستقل
├── config.json                  # تنظیمات (در .gitignore)
├── config.example.json          # نمونه
├── requirements.txt             # کتابخانه‌ها
├── README.md                    # این فایل
├── .gitignore
└── iran_us_news_translated.xlsx # نمونه خروجی

---

## 🚀 نصب و اجرا

### ۱. نصب کتابخانه‌ها

pip install -r requirements.txt

### ۲. ساخت فایل config.json

{
  "telegram_token": "YOUR_TELEGRAM_BOT_TOKEN",
  "channel_id": "YOUR_CHANNEL_ID",
  "my_user_id": "YOUR_USER_ID",
  "groq_api_key": "YOUR_GROQ_API_KEY"
}

### ۳. اجرا

python news_channel_bot.py

---

## 🌐 معماری

RSS (BBC, Al Jazeera, ...)
    ↓
فیلتر (ایران-آمریکا + نفت + طلا)
    ↓
Render Proxy → Groq API (ترجمه)
    ↓
SQLite → ذخیره اخبار
    ↓
ربات تلگرام → ارسال به کانال

---

## 🔐 امنیت

- توکن‌ها در config.json (در .gitignore)
- روی Render از Environment Variables
- config.example.json برای نمونه

---

## 📊 منابع خبری

| منبع | دسته |
|------|------|
| BBC World | عمومی |
| BBC Middle East | خاورمیانه |
| Al Jazeera | خاورمیانه |
| DW English | جهانی |
| France24 | جهانی |
| NYT World | جهانی |

---

## 📝 مجوز

این پروژه برای اهداف آموزشی و شخصی توسعه یافته است.

---

## 👩‍💻 توسعه‌دهنده

KtMir — در حال یادگیری پایتون و فریلنسری

GitHub: @shahgholian2008-create