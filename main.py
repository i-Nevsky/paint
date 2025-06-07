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

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния
STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE, STATE_CHOOSE = range(5)

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_CHOOSE

def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True)
        )
        return STATE_GENDER
    elif text == "Создать анонс к Кофе":
        # Реализуй здесь свой рабочий сценарий анонса (оставляю твой шаблон)
        update.message.reply_text("Введи дату и время (например, 14 марта 13:00 МСК):", reply_markup=ReplyKeyboardRemove())
        return STATE_CITYDATE
    else:
        update.message.reply_text("Нажми одну из кнопок.")
        return STATE_CHOOSE

# Блок Благодарственное письмо ---------------------------------

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    return STATE_FIO

def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        # Открываем шаблон письма
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Шрифты
        font_gender = ImageFont.truetype(BOLD_FONT_PATH, 36)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52)
        font_fam = ImageFont.truetype(BOLD_FONT_PATH, 60)
        font_body = ImageFont.truetype(FONT_PATH, 28)
        font_sign = ImageFont.truetype(FONT_PATH, 28)
        font_footer = ImageFont.truetype(FONT_PATH, 22)

        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # --- Координаты по сетке ---
        x_gender, y_gender = 410, 320
        x_fio, y_fio = 330, 390         # Имя + Отчество
        x_fam, y_fam = 330, 470         # Фамилия
        x_body, y_body = 180, 540       # Основной текст
        w_body = 1100                   # Ширина блока для основного текста
        h_body = 320                    # Высота блока для основного текста
        x_sign, y_sign = 800, 900
        x_footer, y_footer = 1220, 1000

        # --- Имя/фамилия разделение ---
        fio_parts = fio.split()
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""

        # --- Вставляем тексты ---
        # Обращение
        draw.text((x_gender, y_gender), gender, font=font_gender, fill="black")
        # Имя + Отчество
        draw.text((x_fio, y_fio), fio_line1, font=font_fio, fill="black")
        # Фамилия (отдельной строкой, жирно)
        if fio_line2:
            draw.text((x_fam, y_fam), fio_line2, font=font_fam, fill="black")

        # Основной текст с переносом по ширине
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

        body_lines = wrap_text(body, font_body, w_body)
        y_offset = y_body
        for line in body_lines:
            if y_offset > y_body + h_body:
                break
            draw.text((x_body, y_offset), line, font=font_body, fill="black")
            y_offset += font_body.getsize(line)[1] + 8

        # Подпись
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_sign, fill="black")

        # Город и дата
        draw.text((x_footer, y_footer), citydate, font=font_footer, fill="black")

        # Сохраняем и отправляем пользователю
        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    # Вернёмся к стартовому меню
    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_CHOOSE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_city_date)]
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
