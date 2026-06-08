# 🤖 WhatsApp AI Agent — وكيل خدمة العملاء الذكي

وكيل ذكاء اصطناعي يرد على العملاء عبر واتساب بشكل تلقائي.  
مبني بـ **LangGraph + Gemini (OpenRouter) + Twilio + FastAPI**

---

## ⚡ تشغيل كامل في 30 دقيقة

### الخطوة 1 — المتطلبات الأولية (5 دقائق)

تأكد أن عندك:
- Python 3.11+
- حساب على [Twilio](https://www.twilio.com/try-twilio) (مجاني)
- حساب على [OpenRouter](https://openrouter.ai) (مجاني)
- [ngrok](https://ngrok.com/download) مثبّت

---

### الخطوة 2 — إعداد المشروع (5 دقائق)

```bash
# 1. افتح المجلد في VS Code
cd whatsapp_agent

# 2. أنشئ البيئة الافتراضية
python -m venv venv

# 3. فعّل البيئة
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. ثبّت المكتبات
pip install -r requirements.txt
```

---

### الخطوة 3 — إعداد المتغيرات (10 دقائق)
افتح ملف `env.` وأضف القيم:

#### 🔑 Twilio (مجاني):
1. اذهب لـ [console.twilio.com](https://console.twilio.com)
2. من الصفحة الرئيسية انسخ:
   - **Account SID** → `TWILIO_ACCOUNT_SID`
   - **Auth Token** → `TWILIO_AUTH_TOKEN`

#### 🤖 OpenRouter (مجاني):
1. اذهب لـ [openrouter.ai](https://openrouter.ai)
2. سجّل دخول → **API Keys** → **Create Key**
3. انسخ المفتاح → `OPENROUTER_API_KEY`

---

### الخطوة 4 — تشغيل الخادم (2 دقيقة)

```bash
# في Terminal الأول:
python main.py
```

يجب أن ترى:
```
🚀 الخادم يعمل على: http://localhost:8000
📋 Swagger Docs: http://localhost:8000/docs
🔗 Webhook URL: http://localhost:8000/webhook
```

---

### الخطوة 5 — ngrok للـ Webhook (3 دقائق)

```bash
# في Terminal الثاني:
ngrok http 8000
```

ستظهر رسالة مثل:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8000
```

**انسخ الرابط** `https://abc123.ngrok-free.app`

---

### الخطوة 6 — إعداد Twilio Sandbox (5 دقائق)

1. اذهب لـ [Twilio Console → Messaging → WhatsApp Sandbox](https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox)
2. في حقل **"WHEN A MESSAGE COMES IN"** ضع:
   ```
   https://abc123.ngrok-free.app/webhook
   ```
3. اضغط **Save**

#### ربط هاتفك بالـ Sandbox:
1. افتح واتساب على هاتفك
2. أرسل الرسالة المكتوبة في الـ Sandbox (مثل: `join bright-elephant`)
3. للرقم المذكور في الصفحة
4. ستصلك رسالة تأكيد ✅

---

### ✅ ابدأ التجربة!

الآن أرسل أي رسالة من واتساب:
- `مرحبا` ← ترحيب + قائمة رئيسية
- `1` ← تصفح المنتجات
- `2` ← تتبع الطلبات
- `ORD-1001` ← تفاصيل طلب
- `ORD-1002` ← طلب قيد الشحن
- `3` ← الأسئلة الشائعة
- `ما سياسة الإرجاع؟` ← رد مباشر

---

## 📁 هيكل المشروع

```
whatsapp_agent/
├── main.py                 # 🚀 نقطة الدخول — FastAPI + Webhook
├── .env.example            # 🔑 نموذج المتغيرات
├── requirements.txt        # 📦 المكتبات
│
├── agent/
│   ├── graph.py            # 🧠 LangGraph — بناء الـ Graph
│   ├── nodes.py            # ⚙️  وظيفة كل Node
│   ├── state.py            # 📊 تعريف الحالة
│   └── prompts.py          # 💬 الـ System Prompts
│
├── whatsapp/
│   ├── base.py             # 🔌 Abstract Adapter
│   └── twilio_adapter.py   # 📱 تنفيذ Twilio
│
├── tools/
│   └── store_tools.py      # 🛒 أدوات البحث في المتجر
│
└── data/
    ├── products.json        # 🛍️ بيانات المنتجات
    ├── orders.json          # 📦 بيانات الطلبات
    └── faqs.json            # ❓ الأسئلة الشائعة
```

---

## 🔄 تبديل المنصة (الـ Adapter Pattern)

لتغيير منصة واتساب، غيّر سطراً واحداً فقط في `main.py`:

```python
# حالياً:
whatsapp = TwilioAdapter()

# مستقبلاً (مثلاً):
whatsapp = GreenAPIAdapter()
whatsapp = MetaCloudAdapter()
```

---

## 📦 طلبات الديمو الجاهزة

| رقم الطلب | الحالة          |
|-----------|----------------|
| ORD-1001  | ✅ تم التسليم  |
| ORD-1002  | 🚚 قيد الشحن   |
| ORD-1003  | ⏳ قيد المعالجة |
| ORD-1004  | 📦 تم الشحن    |

---

## 🛠️ استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| الوكيل لا يرد | تحقق أن ngrok يعمل وأن الـ Webhook محدّث في Twilio |
| خطأ OpenRouter | تأكد أن مفتاح API صحيح وأن النموذج متاح مجاناً |
| خطأ Twilio auth | تأكد من Account SID و Auth Token |
| الهاتف لا يستقبل | أعد إرسال رسالة الـ Sandbox join |
