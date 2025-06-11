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

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto_bold.ttf")

STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)

COORDS = {
    "gender":   (510, 330),    # Уважаемый/ая
    "name":     (350, 410),    # Имя Отчество
    "surname":  (300, 470),    # Фамилия
    "body":     (170, 540),    # Основной текст
    "footer":   (820, 970),    # Город и дата
}
MAX_WIDTH_BODY = 1050  # ширина основного текста, можешь подправить

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
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True)
        )
        return STATE_FIO
    elif text == "Создать анонс к Кофе":
        update.message.reply_text("Эта функция пока не реализована.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        update.message.reply_text("Выбери действие с помощью кнопки.")
        return STATE_GENDER

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО (Имя Отчество Фамилия):", reply_markup=ReplyKeyboardRemove())
    return STATE_BODY

def get_fio(update, context):
    fio = update.message.text.strip()
    context.user_data["fio"] = fio
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_CITYDATE

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return ConversationHandler.END

def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        f_header = ImageFont.truetype(BOLD_FONT_PATH, 36)
        f_fio = ImageFont.truetype(BOLD_FONT_PATH, 44)
        f_body = ImageFont.truetype(FONT_PATH, 30)
        f_footer = ImageFont.truetype(FONT_PATH, 26)

        # Разбивка ФИО на строки
        fio = context.user_data.get("fio", "")
        fio_parts = fio.split()
        name_part = fio_parts[0] + " " + fio_parts[1] if len(fio_parts) >= 2 else fio
        surname_part = fio_parts[2] if len(fio_parts) == 3 else (fio_parts[-1] if len(fio_parts) > 2 else "")

        # 1. Обращение
        draw.text(COORDS["gender"], context.user_data.get("gender", ""), font=f_header, fill="black")
        # 2. Имя+отчество
        draw.text(COORDS["name"], name_part, font=f_fio, fill="black")
        # 3. Фамилия
        draw.text(COORDS["surname"], surname_part, font=f_fio, fill="black")
        # 4. Основной текст (wrap по ширине)
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            line = ""
            for word in words:
                test_line = line + (" " if line else "") + word
                if font.getsize(test_line)[0] <= max_width:
                    line = test_line
                else:
                    lines.append(line)
                    line = word
            if line:
                lines.append(line)
            return lines
        body_lines = wrap_text(context.user_data.get("body", ""), f_body, MAX_WIDTH_BODY)
        y_offset = COORDS["body"][1]
        for line in body_lines:
            draw.text((COORDS["body"][0], y_offset), line, font=f_body, fill="black")
            y_offset += f_body.getsize(line)[1] + 6
        # 5. Footer (город и дата)
        draw.text(COORDS["footer"], context.user_data.get("citydate", ""), font=f_footer, fill="black")

        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        ConversationHandler.END: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)

dispatcher.add_handler(conv_handler)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
