"""
Family Expense Tracker - Telegram Bot
Nhắn tin với bot Telegram để ghi chép chi tiêu gia đình.
Dữ liệu được lưu vào Google Sheets.
"""

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Chi tiêu gia đình")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB", "")  # Tên tab cụ thể, để trống = sheet1
CHAT_ID = os.getenv("CHAT_ID", "")
PROXY_URL = os.getenv("PROXY_URL", "")  # http://127.0.0.1:7890 nếu dùng proxy
TIMEZONE = timezone(timedelta(hours=7))  # UTC+7 (Vietnam)

# Danh mục chi tiêu và từ khóa
EXPENSE_CATEGORIES = {
    "🍜 Ăn uống": ["ăn", "cơm", "phở", "bún", "trưa", "tối", "sáng", "cà phê", "trà sữa", "nhậu", "bia", "nước", "bánh", "chè", "vặt", "lẩu", "buffet", "hải sản"],
    "🛒 Mua sắm": ["mua", "quần áo", "giày", "dép", "túi", "đồ", "shopee", "lazada", "tiki", "mỹ phẩm", "son", "kem"],
    "🏠 Hóa đơn": ["điện", "nước", "internet", "wifi", "net", "rác", "chung cư", "phí", "bảo hiểm", "thuê nhà", "tiền nhà"],
    "🚗 Di chuyển": ["xăng", "dầu", "gửi xe", "taxi", "grab", "be", "xe bus", "bus", "vé", "bảo dưỡng xe", "rửa xe"],
    "🎓 Học tập": ["học", "sách", "vở", "bút", "gia sư", "học phí", "trường", "lớp", "khóa học"],
    "💊 Sức khỏe": ["thuốc", "bệnh viện", "khám", "bác sĩ", "nha khoa", "răng", "vitamin"],
    "🎉 Giải trí": ["phim", "xem phim", "du lịch", "khách sạn", "karaoke", "game", "netflix", "youtube"],
    "❤️ Gia đình": ["sữa", "bỉm", "tã", "đồ chơi", "bà", "ông", "bố", "mẹ", "con", "quà", "sinh nhật", "cưới", "ma chay"],
    "💸 Khác": [],
}

INCOME_CATEGORIES = {
    "💰 Lương": ["lương", "lương tháng", "salary", "công ty"],
    "💰 Thưởng": ["thưởng", "bonus", "tết", "lì xì", "hoa hồng"],
    "💰 Kinh doanh": ["bán", "buôn", "kinh doanh", "khách", "đơn hàng"],
    "💰 Đầu tư": ["cổ phiếu", "chứng khoán", "lãi", "đầu tư", "cổ tức"],
    "💰 Khác": [],
}

SHEET_HEADERS = ["Ngày", "Loại", "Danh mục", "Số tiền", "Mô tả", "Thời gian"]

# ============================================================
# GOOGLE SHEETS
# ============================================================
def _get_client():
    """Get authorized gspread client."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    if os.path.exists(creds_file):
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
    else:
        import json
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "{}")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
    return gspread.authorize(creds)


def get_sheet():
    """Connect to Google Sheets tab, auto-migrate headers."""
    client = _get_client()
    try:
        spreadsheet = client.open(GOOGLE_SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(GOOGLE_SHEET_NAME)

    # Mở tab cụ thể hoặc sheet1 mặc định
    if GOOGLE_SHEET_TAB:
        try:
            sheet = spreadsheet.worksheet(GOOGLE_SHEET_TAB)
        except gspread.WorksheetNotFound:
            # Tạo tab mới nếu chưa có
            sheet = spreadsheet.add_worksheet(title=GOOGLE_SHEET_TAB, rows=1000, cols=20)
            sheet.append_row(SHEET_HEADERS)
            return sheet
    else:
        sheet = spreadsheet.sheet1

    # Migrate old sheet: add "Loại" column if missing
    headers = sheet.row_values(1)
    if not headers or "Loại" not in headers:
        if headers == ["Ngày", "Danh mục", "Số tiền", "Mô tả", "Thời gian"]:
            # Old format: migrate từ 5 cột sang 6 cột
            all_rows = sheet.get_all_values()
            sheet.clear()
            sheet.append_row(SHEET_HEADERS)
            for row in all_rows[1:]:
                if len(row) >= 5:
                    sheet.append_row([row[0], "Chi", row[1], row[2], row[3], row[4]])
        else:
            # Sheet trống hoặc format lạ → tạo headers mới
            sheet.clear()
            sheet.append_row(SHEET_HEADERS)
    return sheet


def _append_row(entry_type: str, category: str, amount: int, description: str) -> bool:
    """Append a row (Chi or Thu) to Google Sheets."""
    try:
        sheet = get_sheet()
        now = datetime.now(TIMEZONE)
        sheet.append_row([
            now.strftime("%d/%m/%Y"),
            entry_type,
            category,
            amount,
            description,
            now.strftime("%H:%M"),
        ])
        return True
    except Exception as e:
        logging.error("Failed to write to sheet: %s", e)
        return False


def add_expense(category: str, amount: int, description: str) -> bool:
    return _append_row("Chi", category, amount, description)


def add_income(category: str, amount: int, description: str) -> bool:
    return _append_row("Thu", category, amount, description)


def _get_records():
    """Get all records from sheet."""
    sheet = get_sheet()
    return sheet.get_all_records()


def get_today_records(entry_type: str | None = None):
    """Get today's records, optionally filtered by Loại (Chi/Thu)."""
    try:
        records = _get_records()
        today_str = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        result = [r for r in records if r.get("Ngày") == today_str]
        if entry_type:
            result = [r for r in result if r.get("Loại") == entry_type]
        return result
    except Exception as e:
        logging.error("Failed to read sheet: %s", e)
        return []


def get_month_records(entry_type: str | None = None):
    """Get this month's records."""
    try:
        records = _get_records()
        current_month = datetime.now(TIMEZONE).strftime("%m/%Y")
        result = [r for r in records if r.get("Ngày", "").endswith(current_month)]
        if entry_type:
            result = [r for r in result if r.get("Loại") == entry_type]
        return result
    except Exception as e:
        logging.error("Failed to read sheet: %s", e)
        return []


def get_recent_entries(limit: int = 10, entry_type: str | None = None):
    """Get recent entries with their absolute row numbers (1-indexed, row 1 = header)."""
    try:
        sheet = get_sheet()
        all_values = sheet.get_all_values()
        result = []
        for i in range(len(all_values) - 1, 0, -1):
            row = all_values[i]
            if len(row) < 6:
                continue
            row_type = row[1] if len(row) > 1 else ""
            if entry_type and row_type != entry_type:
                continue
            result.append({
                "row_num": i + 1,
                "Ngày": row[0],
                "Loại": row_type,
                "Danh mục": row[2] if len(row) > 2 else "",
                "Số tiền": int(row[3]) if len(row) > 3 and row[3].isdigit() else 0,
                "Mô tả": row[4] if len(row) > 4 else "",
                "Thời gian": row[5] if len(row) > 5 else "",
            })
            if len(result) >= limit:
                break
        return result
    except Exception as e:
        logging.error("Failed to get recent entries: %s", e)
        return []


def delete_entry(row_num: int) -> bool:
    """Delete a row by its absolute row number."""
    try:
        sheet = get_sheet()
        sheet.delete_rows(row_num)
        return True
    except Exception as e:
        logging.error("Failed to delete row %d: %s", row_num, e)
        return False


def update_entry(row_num: int, category: str, amount: int, description: str) -> bool:
    """Update category, amount, description at a given row."""
    try:
        sheet = get_sheet()
        sheet.update(f"C{row_num}", category)
        sheet.update(f"D{row_num}", amount)
        sheet.update(f"E{row_num}", description)
        return True
    except Exception as e:
        logging.error("Failed to update row %d: %s", row_num, e)
        return False


# ============================================================
# PARSER
# ============================================================
def parse_expense(text: str) -> tuple[str, int, str] | None:
    """
    Parse expense from message text.
    Returns (category, amount, description) or None.
    
    Examples:
        "ăn trưa 50k" → ("🍜 Ăn uống", 50000, "ăn trưa")
        "mua sữa cho con 120k" → ("❤️ Gia đình", 120000, "mua sữa cho con")
        "đổ xăng 200" → ("🚗 Di chuyển", 200000, "đổ xăng")
        "cà phê sáng 25" → ("🍜 Ăn uống", 25000, "cà phê sáng")
    """
    text = text.strip().lower()
    
    # Find amount: number followed by k/tr/ngàn/nghìn or just number
    amount_patterns = [
        r'(\d+)\s*k\b',           # 50k, 50 k
        r'(\d+)\s*tr\b',          # 1tr, 1 tr
        r'(\d+)\s*ngàn\b',        # 50 ngàn
        r'(\d+)\s*nghìn\b',       # 50 nghìn
        r'(\d+)\s*triệu\b',       # 1 triệu
        r'(\d{4,})\b',            # 50000 (large number = amount)
    ]
    
    amount = 0
    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            num = int(match.group(1))
            if 'tr' in match.group(0) or 'triệu' in match.group(0):
                amount = num * 1_000_000
            elif 'k' in match.group(0) or 'ngàn' in match.group(0) or 'nghìn' in match.group(0):
                amount = num * 1_000
            elif num >= 1000:
                amount = num  # assume it's already in VND
            else:
                amount = num * 1_000  # small number like 50 → 50k
            break
    
    if amount == 0:
        return None
    
    # Remove amount from text to get description
    description = re.sub(r'\d+\s*(k|tr|ngàn|nghìn|triệu)?\b', '', text).strip()
    if not description:
        description = text
    
    # Categorize
    category = "💸 Khác"
    for cat, keywords in EXPENSE_CATEGORIES.items():
        for kw in keywords:
            if kw in description:
                category = cat
                break
        if category != "💸 Khác":
            break
    
    return category, amount, description


# ============================================================
# TELEGRAM BOT HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome = """👋 *Chào mừng đến với Bot Quản Lý Chi Tiêu Gia Đình!*

Bạn chỉ cần nhắn tin theo cú pháp:
`[mô tả] [số tiền]`

*Ví dụ:*
• `ăn trưa 50k`
• `mua sữa cho con 120k`
• `đổ xăng 200k`
• `tiền điện tháng này 850k`

*Lệnh:*
/add [mô tả] [số tiền] - Thêm chi tiêu
/homnay - Xem chi tiêu hôm nay
/thangnay - Tổng chi tiêu tháng này
/baocao - Link Google Sheet
/help - Hướng dẫn"""
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """📖 *Hướng dẫn sử dụng:*

*Thêm chi tiêu:* Nhắn `/add [mô tả] [số tiền]`
Hoặc đơn giản nhắn: `[mô tả] [số tiền]`

*Xem chi tiêu:*
/homnay - Danh sách chi tiêu hôm nay
/thangnay - Tổng kết chi tiêu tháng này
/baocao - Link Google Sheet

*Danh mục tự động:*
🍜 Ăn uống | 🛒 Mua sắm | 🏠 Hóa đơn
🚗 Di chuyển | 🎓 Học tập | 💊 Sức khỏe
🎉 Giải trí | ❤️ Gia đình | 💸 Khác"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def add_expense_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command."""
    text = update.message.text
    
    # Remove /add prefix
    if text.startswith("/add"):
        text = text[4:].strip()
    
    if not text:
        await update.message.reply_text("❌ Vui lòng nhập: `/add [mô tả] [số tiền]`\nVí dụ: `/add ăn trưa 50k`", parse_mode="Markdown")
        return
    
    result = parse_expense(text)
    if result is None:
        await update.message.reply_text("❌ Không tìm thấy số tiền. Vui lòng nhập kèm số tiền.\nVí dụ: `ăn trưa 50k` hoặc `mua đồ 120000`", parse_mode="Markdown")
        return
    
    category, amount, description = result
    
    if add_expense(category, amount, description):
        await update.message.reply_text(
            f"✅ *Đã ghi nhận!*\n"
            f"📂 {category}\n"
            f"💰 {amount:,}đ\n"
            f"📝 {description}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Lỗi khi ghi dữ liệu. Vui lòng thử lại sau.")


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /homnay command."""
    records = get_today_records("Chi")
    
    if not records:
        await update.message.reply_text("📭 Hôm nay chưa có chi tiêu nào.")
        return
    
    total = sum(r.get("Số tiền", 0) for r in records)
    
    lines = [f"📊 *Chi tiêu hôm nay ({len(records)} khoản)*\n"]
    for r in records:
        cat = r.get("Danh mục", "")
        amount = r.get("Số tiền", 0)
        desc = r.get("Mô tả", "")
        lines.append(f"{cat} `{amount:,}đ` - {desc}")
    
    lines.append(f"\n💰 *Tổng: {total:,}đ*")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def month_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /thangnay command."""
    records = get_month_records("Chi")
    
    if not records:
        await update.message.reply_text("📭 Tháng này chưa có chi tiêu nào.")
        return
    
    total = sum(r.get("Số tiền", 0) for r in records)
    
    # Group by category
    by_cat = {}
    for r in records:
        cat = r.get("Danh mục", "💸 Khác")
        amount = r.get("Số tiền", 0)
        by_cat[cat] = by_cat.get(cat, 0) + amount
    
    lines = [f"📊 *Tổng kết chi tiêu tháng này ({len(records)} khoản)*\n"]
    
    for cat, amount in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
        pct = amount / total * 100 if total > 0 else 0
        lines.append(f"{cat}: `{amount:,}đ` ({pct:.0f}%)")
    
    lines.append(f"\n💰 *Tổng: {total:,}đ*")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /baocao command - send Google Sheet link."""
    sheet_name = GOOGLE_SHEET_NAME
    sheet_url = f"https://docs.google.com/spreadsheets/d/1... (mở Google Sheets để xem)"
    
    try:
        sheet = get_sheet()
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet.spreadsheet.id}"
    except:
        pass
    
    await update.message.reply_text(
        f"📊 *Google Sheet Chi Tiêu Gia Đình:*\n{sheet_url}",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trả về chat_id của người dùng."""
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🆔 Chat ID của bạn: `{cid}`\n\nCopy giá trị này vào `CHAT_ID` trong file `.env`.",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages - try to parse as expense."""
    text = update.message.text.strip()
    
    # Skip commands
    if text.startswith("/"):
        return
    
    # Try to parse as expense
    result = parse_expense(text)
    if result:
        category, amount, description = result
        
        if add_expense(category, amount, description):
            await update.message.reply_text(
                f"✅ *Đã ghi nhận!*\n"
                f"📂 {category}\n"
                f"💰 {amount:,}đ\n"
                f"📝 {description}\n\n"
                f"_Dùng /homnay để xem chi tiêu hôm nay_",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Lỗi khi ghi dữ liệu.")
    else:
        # Not an expense message - show help
        await update.message.reply_text(
            "👋 Để ghi chi tiêu, nhắn theo cú pháp:\n"
            "`[mô tả] [số tiền]`\n\n"
            "Ví dụ: `ăn trưa 50k`\n\n"
            "Gõ /help để xem hướng dẫn đầy đủ.",
            parse_mode="Markdown"
        )


# ============================================================
# MAIN
# ============================================================
def main():
    """Start the bot."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO,
    )
    
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    # Build app with proxy if configured
    builder = Application.builder().token(TELEGRAM_TOKEN)
    if PROXY_URL:
        builder.proxy(PROXY_URL)
        logging.info("Using proxy: %s", PROXY_URL)
    app = builder.build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_expense_cmd))
    app.add_handler(CommandHandler("homnay", today_cmd))
    app.add_handler(CommandHandler("thangnay", month_cmd))
    app.add_handler(CommandHandler("baocao", report_cmd))
    app.add_handler(CommandHandler("myid", myid_cmd))

    # Message handler (for natural language input)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Gửi thông báo khởi động sau khi bot initialized
    async def on_startup(app_instance):
        logging.info("🤖 Expense Tracker Bot started!")
        if CHAT_ID:
            try:
                await app_instance.bot.send_message(
                    chat_id=CHAT_ID,
                    text="✅ *Bot đã khởi động!*\n📝 Sẵn sàng nhận chi tiêu hôm nay.\n\nNhắn: `[mô tả] [số tiền]`\nVí dụ: `ăn trưa 50k`",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.warning("Không gửi được thông báo khởi động: %s", e)

    app.post_init = on_startup

    app.run_polling()


if __name__ == "__main__":
    main()
