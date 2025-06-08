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

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния
STATE_MODE, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(5)

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_MODE

def choose_mode(update, context):
    if update.message.text == "Создать благ. письмо ФАБА":
        kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return STATE_GENDER

    update.message.reply_text("Эта функция пока не реализована.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def get_gender(update, context):
    context.user_data["gender"] = update.message.text
    update.message.reply_text("Введите ФИО (Имя Отчество):", reply_markup=ReplyKeyboardRemove())
    return STATE_FIO

def get_fio(update, context):
    # сохраняем полное ФИО, распишем потом на две строки
    context.user_data["full_fio"] = update.message.text
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text

    # Открываем изображение
    base = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # Шрифты
    font_gender = ImageFont.truetype(BOLD_FONT_PATH, 36)
    font_name = ImageFont.truetype(BOLD_FONT_PATH, 52)
    font_body = ImageFont.truetype(FONT_PATH, 28)
    font_footer = ImageFont.truetype(FONT_PATH, 22)

    # Тексты и координаты по твоему ТЗ
    gender = context.user_data["gender"]
    # Раскладываем ФИО на имя+отчество и фамилию
    parts = context.user_data["full_fio"].split()
    if len(parts) >= 2:
        name_part = " ".join(parts[:-1])
        surname = parts[-1]
    else:
        name_part = context.user_data["full_fio"]
        surname = ""

    body = context.user_data["body"]
    citydate = context.user_data["citydate"]

    # Новые координаты:
    # Обращение
    draw.text((500, 420), gender, font=font_gender, fill="black")
    # Имя и отчество
    draw.text((320, 510), name_part, font=font_name, fill="black")
    # Фамилия
    draw.text((250, 600), surname, font=font_name, fill="black")
    # Основной текст
    def wrap(text, fnt, max_w):
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if fnt.getsize(test)[0] <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    lines = wrap(body, font_body, 970)
    y = 740
    for ln in lines:
        draw.text((200, y), ln, font=font_body, fill="black")
        y += font_body.getsize(ln)[1] + 6

    # Город и дата
    draw.text((1350, 1370), citydate, font=font_footer, fill="black")

    # Отправляем результат
    bio = io.BytesIO()
    base.save(bio, format="PNG")
    bio.seek(0)
    update.message.reply_photo(photo=bio, caption="Готово!", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_MODE:   [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO:    [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY:   [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
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
    return "Service up"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
