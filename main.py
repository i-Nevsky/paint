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
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
GRAT_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния
(STATE_CHOOSE, STATE_GRAT_GENDER, STATE_GRAT_FIO, STATE_GRAT_BODY, STATE_GRAT_CITYDATE,
 STATE_COFFEE_DT, STATE_COFFEE_FIO, STATE_COFFEE_TOPIC, STATE_COFFEE_PHOTO) = range(9)

# Старт
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_CHOOSE

# Обработка выбора
def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return STATE_GRAT_GENDER
    elif text == "Создать анонс к Кофе":
        update.message.reply_text("Введи дату и время (например, 14 марта 13:00 МСК):", reply_markup=ReplyKeyboardRemove())
        return STATE_COFFEE_DT
    else:
        update.message.reply_text("Выберите действие с помощью кнопки.")
        return STATE_CHOOSE

# ------------------------ Благодарственное письмо ------------------------
def grat_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    return STATE_GRAT_FIO

def grat_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_GRAT_BODY

def grat_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_GRAT_CITYDATE

def grat_citydate(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        base_image = Image.open(GRAT_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        font_header = ImageFont.truetype(BOLD_FONT_PATH, 36)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52)
        font_body = ImageFont.truetype(FONT_PATH, 28)
        font_sign = ImageFont.truetype(FONT_PATH, 28)
        font_footer = ImageFont.truetype(FONT_PATH, 22)
        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # --- Координаты (выверено по шаблону, можно подогнать):
        x_gender, y_gender = 345, 285
        x_fio, y_fio = 220, 350
        x_body, y_body, w_body = 150, 460, 950
        x_sign, y_sign = 420, 845
        x_footer, y_footer = 565, 1090

        # Обращение
        draw.text((x_gender, y_gender), gender, font=font_header, fill="black")

        # ФИО (две строки, если три слова)
        fio_parts = fio.split()
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""
        draw.text((x_fio, y_fio), fio_line1, font=font_fio, fill="black")
        if fio_line2:
            draw.text((x_fio, y_fio + 55), fio_line2, font=font_fio, fill="black")

        # Основной текст с переносами по ширине
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
            draw.text((x_body, y_offset), line, font=font_body, fill="black")
            y_offset += font_body.getsize(line)[1] + 6

        # Подпись
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_sign, fill="black")
        # Город и дата
        draw.text((x_footer, y_footer), citydate, font=font_footer, fill="black")

        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    return start(update, context)

# ------------------------ Анонс к Кофе ------------------------
def coffee_dt(update, context):
    context.user_data["coffee_dt"] = update.message.text.strip()
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return STATE_COFFEE_FIO

def coffee_fio(update, context):
    context.user_data["coffee_fio"] = update.message.text.strip()
    update.message.reply_text("Напиши тему эфира:")
    return STATE_COFFEE_TOPIC

def coffee_topic(update, context):
    context.user_data["coffee_topic"] = update.message.text.strip()
    update.message.reply_text("Отправь фото эксперта:")
    return STATE_COFFEE_PHOTO

def coffee_photo(update, context):
    try:
        if update.message.photo:
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")

            base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
            draw = ImageDraw.Draw(base_image)
            font_dt = ImageFont.truetype(FONT_PATH, 45)
            font_fio = ImageFont.truetype(FONT_PATH, 65)
            font_topic = ImageFont.truetype(FONT_PATH, 55)

            # Дата/время
            draw.text((40, 35), context.user_data["coffee_dt"], font=font_dt, fill="white")

            # ФИО
            draw.rectangle((40, 220, 510, 330), fill=(0,0,0,180))
            draw.text((60, 240), context.user_data["coffee_fio"], font=font_fio, fill="white")

            # Тема
            draw.rectangle((40, 340, 510, 440), fill=(0,0,0,180))
            draw.text((60, 360), context.user_data["coffee_topic"], font=font_topic, fill="white")

            # Фото эксперта (круг)
            circle_diameter = 300
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS, centering=(0.5, 0.3))
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            temp_layer = Image.new("RGBA", (circle_diameter, circle_diameter), (0, 0, 0, 0))
            temp_layer.paste(user_photo, (0, 0), user_photo)
            base_image.alpha_composite(temp_layer, (360, 70))

            out_stream = io.BytesIO()
            base_image.convert("RGB").save(out_stream, format="JPEG")
            out_stream.seek(0)
            update.message.reply_photo(photo=out_stream, caption="Анонс готов!")
        else:
            update.message.reply_text("Пожалуйста, отправь изображение.")
            return STATE_COFFEE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании анонса: {e}")

    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_CHOOSE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GRAT_GENDER: [MessageHandler(Filters.text & ~Filters.command, grat_gender)],
        STATE_GRAT_FIO: [MessageHandler(Filters.text & ~Filters.command, grat_fio)],
        STATE_GRAT_BODY: [MessageHandler(Filters.text & ~Filters.command, grat_body)],
        STATE_GRAT_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, grat_citydate)],
        STATE_COFFEE_DT: [MessageHandler(Filters.text & ~Filters.command, coffee_dt)],
        STATE_COFFEE_FIO: [MessageHandler(Filters.text & ~Filters.command, coffee_fio)],
        STATE_COFFEE_TOPIC: [MessageHandler(Filters.text & ~Filters.command, coffee_topic)],
        STATE_COFFEE_PHOTO: [MessageHandler(Filters.photo, coffee_photo)]
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
