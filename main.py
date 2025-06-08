import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
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

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

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
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True)
        )
        return STATE_FIO
    elif text == "Создать анонс к Кофе":
        update.message.reply_text("Эта функция пока не реализована.")
        return ConversationHandler.END

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:")
    return STATE_BODY

def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
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

        # Настрой шрифтов (размеры отрегулированы под сетку)
        font_header = ImageFont.truetype(BOLD_FONT_PATH, 38)     # Обращение
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 46)        # Имя Отчество
        font_fio2 = ImageFont.truetype(BOLD_FONT_PATH, 60)       # Фамилия
        font_body = ImageFont.truetype(FONT_PATH, 24)            # Основной текст
        font_footer = ImageFont.truetype(FONT_PATH, 22)          # Подпись и город/дата

        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # ФИО разбиваем на Имя Отчество и Фамилию
        fio_parts = fio.split()
        fio_line1, fio_line2 = "", ""
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""

        # ====== ТОЧНЫЕ КООРДИНАТЫ (по твоей сетке) ======
        # Обращение
        x_gender, y_gender = 500, 420
        # Имя Отчество
        x_fio1, y_fio1 = 320, 510
        # Фамилия
        x_fio2, y_fio2 = 250, 600
        # Основной текст (переносим по ширине)
        x_body, y_body = 200, 740
        max_width_body = 1000
        # Подпись (оставляю старое место, по твоему шаблону ~350, 1250)
        x_sign, y_sign = 350, 1250
        # Город и дата
        x_footer, y_footer = 1350, 1370

        draw.text((x_gender, y_gender), gender, font=font_header, fill="black")
        draw.text((x_fio1, y_fio1), fio_line1, font=font_fio, fill="black")
        draw.text((x_fio2, y_fio2), fio_line2, font=font_fio2, fill="black")

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

        body_lines = wrap_text(body, font_body, max_width_body)
        y_offset = y_body
        for line in body_lines:
            draw.text((x_body, y_offset), line, font=font_body, fill="black")
            y_offset += font_body.getsize(line)[1] + 8

        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_footer, fill="black")
        draw.text((x_footer, y_footer), citydate, font=font_footer, fill="black")

        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")
    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        ConversationHandler.END: [MessageHandler(Filters.text & ~Filters.command, get_city_date)]
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
