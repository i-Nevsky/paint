import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Flask + Telegram setup
app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ВАШ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к ресурсам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH        = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH   = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния разговора
STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_GENDER

def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return STATE_FIO

    # сюда позже можно добавить логику анонса к Кофе
    update.message.reply_text("Эта функция пока не реализована.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    return STATE_BODY

def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY + 1  # временный переход к STATE_BODY для ввода текста

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text(
        "Введите город и дату (например: г. Краснодар, май 2025):",
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_CITYDATE

def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text.strip()

    # Загружаем шаблон
    img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Шрифты
    f_gen     = ImageFont.truetype(BOLD_FONT_PATH, 36)  # Обращение
    f_name    = ImageFont.truetype(BOLD_FONT_PATH, 52)  # Имя+Отчество
    f_surname = ImageFont.truetype(BOLD_FONT_PATH, 52)  # Фамилия
    f_body    = ImageFont.truetype(FONT_PATH,        28)  # Текст благодарности
    f_footer  = ImageFont.truetype(FONT_PATH,        22)  # Город/дата

    # Новые координаты по вашей сетке
    coords = {
        "gender":  (650, 450),
        "name":    (650, 550),
        "surname": (650, 650),
        "body":    (350, 750),
        "sign":    (400, 810),   # здесь просто подпись-статичный текст
        "footer":  (650, 1350),
    }

    gender = context.user_data["gender"]
    fio     = context.user_data["fio"]
    body    = context.user_data["body"]
    citydt  = context.user_data["citydate"]

    # 1) Обращение
    draw.text(coords["gender"], gender, font=f_gen, fill="black")

    # 2) ФИО: если три слова — разбиваем
    parts = fio.split()
    if len(parts) == 3:
        nm = f"{parts[0]} {parts[1]}"
        sr = parts[2]
    else:
        nm, sr = fio, ""
    draw.text(coords["name"], nm, font=f_name, fill="black")
    if sr:
        draw.text((coords["surname"][0], coords["surname"][1]), sr, font=f_surname, fill="black")

    # 3) Основной текст — делаем перенос по ширине 1000px
    x0, y0 = coords["body"]
    max_w   = 1000
    lines = []
    for word in body.split():
        test = (lines[-1] + " " + word) if lines else word
        w, _ = f_body.getsize(test)
        if w < max_w:
            if lines:
                lines[-1] = test
            else:
                lines = [test]
        else:
            lines.append(word)
    y = y0
    for line in lines:
        draw.text((x0, y), line, font=f_body, fill="black")
        y += f_body.getsize(line)[1] + 6

    # 4) Подпись (статичный текст)
    sign_txt = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
    draw.text(coords["sign"], sign_txt, font=f_body, fill="black")

    # 5) Город и дата
    draw.text(coords["footer"], citydt, font=f_footer, fill="black")

    # Сохраняем в буфер и отправляем
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    update.message.reply_photo(photo=buf, caption="Готово!")

    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_GENDER:  [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_FIO:     [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_BODY:    [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY+1:  [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE:[MessageHandler(Filters.text & ~Filters.command, get_city_date)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route("/")
def index():
    return "Bot is running"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
