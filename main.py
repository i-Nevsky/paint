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
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto_bold.ttf")  # можешь заменить если нет

# Состояния
STATE_CHOOSE, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(5)

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
        update.message.reply_text("Эта функция пока не реализована.")
        return ConversationHandler.END
    else:
        update.message.reply_text("Пожалуйста, выбери действие из меню.")
        return STATE_CHOOSE

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
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Шрифты
        font_gender = ImageFont.truetype(FONT_PATH, 32)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 48)
        font_surname = ImageFont.truetype(BOLD_FONT_PATH, 68)
        font_body = ImageFont.truetype(FONT_PATH, 30)
        font_sign = ImageFont.truetype(FONT_PATH, 26)
        font_footer = ImageFont.truetype(FONT_PATH, 22)

        # Получаем данные
        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # --- 1. "Уважаемый/ая" — по центру, 32pt ---
        gender_x = 440
        gender_y = 315
        draw.text((gender_x, gender_y), gender, font=font_gender, fill="black")

        # --- 2. Имя Отчество и Фамилия ---
        fio_parts = fio.strip().split()
        if len(fio_parts) == 3:
            name_otch = f"{fio_parts[0]} {fio_parts[1]}"
            surname = fio_parts[2]
        else:
            name_otch = fio
            surname = ""

        # Имя Отчество — по центру, жирный, 48pt
        w_name, _ = draw.textsize(name_otch, font=font_fio)
        x_name = (base_image.width - w_name) // 2
        draw.text((x_name, 390), name_otch, font=font_fio, fill="black")

        # Фамилия — по центру, жирный, 68pt
        w_surname, _ = draw.textsize(surname, font=font_surname)
        x_surname = (base_image.width - w_surname) // 2
        draw.text((x_surname, 470), surname, font=font_surname, fill="black")

        # --- 3. Основной текст — перенос по ширине ---
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            line = ""
            for word in words:
                test_line = line + (" " if line else "") + word
                if draw.textsize(test_line, font=font)[0] <= max_width:
                    line = test_line
                else:
                    if line:
                        lines.append(line)
                    line = word
            if line:
                lines.append(line)
            return lines

        x_body, y_body = 150, 570
        w_body = 950
        body_lines = wrap_text(body, font_body, w_body)
        for line in body_lines:
            draw.text((x_body, y_body), line, font=font_body, fill="black")
            y_body += font_body.getsize(line)[1] + 6

        # --- 4. Подпись ---
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        sign_y = 1030
        for line in sign_text.split('\n'):
            w_sign, _ = draw.textsize(line, font=font_sign)
            draw.text(((base_image.width - w_sign)//2, sign_y), line, font=font_sign, fill="black")
            sign_y += font_sign.getsize(line)[1] + 1

        # --- 5. Город, дата ---
        w_footer, _ = draw.textsize(citydate, font=font_footer)
        draw.text(((base_image.width-w_footer)//2, 1075), citydate, font=font_footer, fill="black")

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
