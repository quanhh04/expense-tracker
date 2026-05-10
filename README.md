# 🏠 Bot Quản Lý Chi Tiêu Gia Đình

Nhắn tin Telegram → Tự động ghi vào Google Sheets

---

## 🚀 Cài đặt nhanh (3 bước)

### Bước 1: Tạo Telegram Bot

1. Mở Telegram, tìm [@BotFather](https://t.me/BotFather)
2. Nhắn `/newbot` → Đặt tên → Nhận **Token**
3. Copy token vào `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABCdef...
   ```

### Bước 2: Tạo Google Service Account

1. Vào [Google Cloud Console](https://console.cloud.google.com)
2. Tạo project mới → **APIs & Services** → **Enable APIs**
3. Bật **Google Sheets API** + **Google Drive API**
4. **Credentials** → **Create Service Account**
5. Đặt tên → **Done**
6. Vào Service Account → **Keys** → **Add Key** → **JSON**
7. Tải file JSON về, đặt tên `credentials.json` trong thư mục project

### Bước 3: Chạy bot

```powershell
cd D:\trantu\code\expense-tracker
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Sửa .env với TELEGRAM_BOT_TOKEN của bạn
python main.py
```

---

## 📱 Cách sử dụng

### Thêm chi tiêu

```
ăn trưa 50k
mua sữa cho con 120k
đổ xăng 200k
tiền điện tháng này 850k
```

### Xem báo cáo

| Lệnh | Chức năng |
|------|-----------|
| `/homnay` | Chi tiêu hôm nay |
| `/thangnay` | Tổng kết tháng này |
| `/baocao` | Link Google Sheet |
| `/help` | Hướng dẫn |

---

## 🗂️ Danh mục tự động

Bot tự phân loại dựa trên từ khóa:

| Danh mục | Từ khóa |
|----------|---------|
| 🍜 Ăn uống | ăn, cơm, phở, cà phê, trà sữa... |
| 🛒 Mua sắm | mua, quần áo, shopee, lazada... |
| 🏠 Hóa đơn | điện, nước, internet, tiền nhà... |
| 🚗 Di chuyển | xăng, grab, taxi, gửi xe... |
| 🎓 Học tập | học, sách, học phí... |
| 💊 Sức khỏe | thuốc, bệnh viện, khám... |
| 🎉 Giải trí | phim, du lịch, karaoke... |
| ❤️ Gia đình | sữa, bỉm, quà, sinh nhật... |
| 💸 Khác | (mặc định) |

---

## ☁️ Deploy lên Render (Free)

1. Push code lên GitHub
2. Render → New Web Service → Connect repo
3. Settings:
   - **Runtime**: Python
   - **Build**: `pip install -r requirements.txt`
   - **Start**: `python main.py`
4. Env vars:
   - `TELEGRAM_BOT_TOKEN`
   - `GOOGLE_CREDENTIALS_JSON` (paste toàn bộ JSON credentials)
   - `GOOGLE_SHEET_NAME`

---

## 📊 Google Sheet mẫu

| Ngày | Danh mục | Số tiền | Mô tả | Thời gian |
|------|----------|---------|-------|-----------|
| 10/05/2026 | 🍜 Ăn uống | 50000 | ăn trưa | 12:30 |
| 10/05/2026 | 🚗 Di chuyển | 200000 | đổ xăng | 17:45 |
| 10/05/2026 | 🛒 Mua sắm | 350000 | mua quần áo | 20:00 |
