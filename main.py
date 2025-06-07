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
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto_bold.ttf")  # можно скачать или оставить FONT_PATH

# Состояния
STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)

# Стартовый обработчик с кнопкой
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_GENDER

# Обработчик выбора типа письма (сейчас реализован только gratitude)
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

# Получение обращения (Уважаемый/Уважаемая)
def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:")
    return STATE_BODY

# Получение ФИО
def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_CITYDATE

# Получение основного текста
def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return ConversationHandler.END

# После получения города и даты формируем письмо
def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        # Открываем шаблон письма
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Настройка шрифтов (поставь свой шрифт или скачай roboto_bold.ttf если нужен жирный)
        font_header = ImageFont.truetype(BOLD_FONT_PATH, 36)  # "Уважаемый"
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52)
        font_body = ImageFont.truetype(FONT_PATH, 28)
        font_sign = ImageFont.truetype(FONT_PATH, 28)
        font_footer = ImageFont.truetype(FONT_PATH, 22)

        # 1. Обращение (Уважаемый...)
        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # Координаты (по твоей сетке и макету)
        # -- Обращение
        x_gender, y_gender = 300, 270
        # -- ФИО (можно две строки, см. твой образец)
        x_fio, y_fio = 230, 340
        # -- Основной текст
        x_body, y_body, w_body, h_body = 120, 420, 970, 350  # h_body = до 770 (500,1050 на сетке)
        # -- Подпись
        x_sign, y_sign = 400, 810
        # -- Город и дата
        x_footer, y_footer = 545, 1075

        # 1. Обращение (всегда одна строка)
        draw.text((x_gender, y_gender), gender, font=font_header, fill="black")

        # 2. ФИО (делим на две строки: имя+отчество и фамилия, если три слова)
        fio_parts = fio.split()
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""
        draw.text((x_fio, y_fio), fio_line1, font=font_fio, fill="black")
        draw.text((x_fio, y_fio + 55), fio_line2, font=font_fio, fill="black")

        # 3. Основной текст с переносами по ширине
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

        # 4. Подпись — фиксированный текст
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_sign, fill="black")

        # 5. Город и дата
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
