import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters
from PIL import Image, ImageDraw, ImageFont

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)

# --- Flask и Telegram Bot ---
app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "ВАШ_ТОКЕН_СЮДА"
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# --- Пути к ресурсам ---
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_REGULAR    = os.path.join(os.getcwd(), "static", "roboto.ttf")
FONT_BOLD       = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# --- Состояния диалога ---
STATE_CHOOSE, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(5)

# --- Координаты из последнего ТЗ ---
COORDS = {
    "gender":  (510, 330),   # Обращение
    "name":    (350, 410),   # Имя + отчество
    "surname": (300, 470),   # Фамилия
    "body":    (170, 540),   # Основной текст
    "footer":  (820, 970),   # Город и дата
}
MAX_WIDTH_BODY = 1000  # ширина области для переноса строк

# --- /start ---
def start(update: Update, context):
    context.user_data.clear()
    keyboard = [["Создать благ. письмо ФАБА"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return STATE_CHOOSE

# --- Выбор режима ---
def choose_mode(update: Update, context):
    if update.message.text == "Создать благ. письмо ФАБА":
        kb = [["Уважаемый", "Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_GENDER
    update.message.reply_text("Неизвестная команда.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Получаем обращение ---
def get_gender(update: Update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО (Имя Отчество Фамилия):", reply_markup=ReplyKeyboardRemove())
    return STATE_FIO

# --- Получаем ФИО ---
def get_fio(update: Update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

# --- Получаем основной текст ---
def get_body(update: Update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text(
        "Введите город и дату (например: г. Краснодар, май 2025):",
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_CITYDATE

# --- Финальный шаг: отрисовка и отправка ---
def get_citydate(update: Update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        # Открываем шаблон
        img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Загружаем шрифты
        f_gen  = ImageFont.truetype(FONT_BOLD,    36)
        f_name = ImageFont.truetype(FONT_BOLD,    52)
        f_body = ImageFont.truetype(FONT_REGULAR, 28)
        f_foot = ImageFont.truetype(FONT_REGULAR, 22)

        # 1) Обращение
        draw.text(COORDS["gender"], context.user_data["gender"], font=f_gen, fill="black")

        # 2) Имя + Отчество и Фамилия
        parts = context.user_data["fio"].split()
        if len(parts) >= 3:
            line1 = f"{parts[0]} {parts[1]}"
            line2 = parts[2]
        else:
            line1 = context.user_data["fio"]
            line2 = ""
        draw.text(COORDS["name"], line1, font=f_name, fill="black")
        if line2:
            draw.text(COORDS["surname"], line2, font=f_name, fill="black")

        # 3) Основной текст с переносом по ширине
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if font.getsize(test)[0] <= max_width:
                    cur = test
                else:
                    lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            return lines

        lines = wrap_text(context.user_data["body"], f_body, MAX_WIDTH_BODY)
        y = COORDS["body"][1]
        for ln in lines:
            draw.text((COORDS["body"][0], y), ln, font=f_body, fill="black")
            y += f_body.getsize(ln)[1] + 6

        # 4) Подпись (фиксированный текст)
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text(COORDS["sign"], sign_text, font=f_body, fill="black")

        # 5) Город и дата
        draw.text(COORDS["footer"], context.user_data["citydate"], font=f_foot, fill="black")

        # Отправляем
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        buf.seek(0)
        update.message.reply_photo(photo=buf, caption="Готово!", reply_markup=ReplyKeyboardRemove())

    except Exception as e:
        logging.exception("Ошибка при создании письма")
        update.message.reply_text(f"Ошибка при создании письма: {e}", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

# --- Отмена ---
def cancel(update: Update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Регистрируем ConversationHandler ---
conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_CHOOSE:   [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER:   [MessageHandler(Filters.regex("^(Уважаемый|Уважаемая)$"), get_gender)],
        STATE_FIO:      [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY:     [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_citydate)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)

# --- Вебхук и запуск ---
@app.route("/webhook", methods=["POST"])
def webhook():
    upd = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(upd)
    return "ok", 200

@app.route("/")
def index():
    return "Сервис Telegram бота работает"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
