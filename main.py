import logging
import os
import io
from flask import Flask, request
from telegram import (
    Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont

# === Настройки ===
app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto_bold.ttf")

# Координаты по сетке (по последним твоим данным)
COORDS = {
    "gender":   (510, 330),   # «Уважаемый»
    "name":     (350, 410),   # Имя + Отчество
    "surname":  (300, 470),   # Фамилия
    "body":     (170, 540),   # Основной текст
    "footer":   (820, 970),   # Город и дата
}

STATE_START, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(5)

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data.clear()
    return STATE_START

def choose_mode(update, context):
    text = update.message.text.strip()
    if text == "Создать благ. письмо ФАБА":
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True)
        )
        return STATE_GENDER
    elif text == "Создать анонс к Кофе":
        update.message.reply_text("Эта функция пока не реализована.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        update.message.reply_text("Выберите действие с помощью кнопок.")
        return STATE_START

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО (например: Иванов Иван Иванович):", reply_markup=ReplyKeyboardRemove())
    return STATE_FIO

def get_fio(update, context):
    fio = update.message.text.strip()
    fio_parts = fio.split()
    if len(fio_parts) == 3:
        context.user_data["surname"] = fio_parts[0]
        context.user_data["name"] = fio_parts[1] + " " + fio_parts[2]
    elif len(fio_parts) == 2:
        context.user_data["surname"] = fio_parts[0]
        context.user_data["name"] = fio_parts[1]
    else:
        context.user_data["surname"] = fio
        context.user_data["name"] = ""
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

def get_citydate(update, context):
    context.user_data["footer"] = update.message.text.strip()
    # == Создаём изображение ==
    try:
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        # Шрифты
        f_gender = ImageFont.truetype(BOLD_FONT_PATH, 36)
        f_name   = ImageFont.truetype(BOLD_FONT_PATH, 36)
        f_surname = ImageFont.truetype(BOLD_FONT_PATH, 36)
        f_body   = ImageFont.truetype(FONT_PATH, 28)
        f_footer = ImageFont.truetype(FONT_PATH, 22)
        # Обращение
        draw.text(COORDS["gender"], context.user_data["gender"], font=f_gender, fill="black")
        # Имя + Отчество
        draw.text(COORDS["name"], context.user_data["name"], font=f_name, fill="black")
        # Фамилия
        draw.text(COORDS["surname"], context.user_data["surname"], font=f_surname, fill="black")
        # Основной текст (с переносом по ширине)
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                if font.getsize(test)[0] <= max_width:
                    current = test
                else:
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)
            return lines
        max_width_body = 1000
        lines = wrap_text(context.user_data["body"], f_body, max_width_body)
        y_offset = COORDS["body"][1]
        for line in lines:
            draw.text((COORDS["body"][0], y_offset), line, font=f_body, fill="black")
            y_offset += f_body.getsize(line)[1] + 8
        # Город и дата
        draw.text(COORDS["footer"], context.user_data["footer"], font=f_footer, fill="black")
        # Отправка
        out = io.BytesIO()
        base_image.save(out, format="PNG")
        out.seek(0)
        update.message.reply_photo(photo=out, caption="Готово!", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logging.error(f"Ошибка при создании письма: {e}")
        update.message.reply_text(f"Ошибка при создании письма: {e}", reply_markup=ReplyKeyboardRemove())
    # Вернуть в главное меню
    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_START:   [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER:  [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO:     [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY:    [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE:[MessageHandler(Filters.text & ~Filters.command, get_citydate)],
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
