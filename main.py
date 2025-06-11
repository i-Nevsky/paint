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
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto_bold.ttf")  # Если нету, используй FONT_PATH

# Координаты по твоей разметке
COORDS = {
    "gender":  (510, 330),   # «Уважаемый»
    "fio1":    (350, 410),   # Имя + Отчество
    "fio2":    (300, 470),   # Фамилия
    "body":    (170, 540),   # Основной текст
    "footer":  (820, 970),   # Город и дата
}

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
        update.message.reply_text("Эта функция пока не реализована.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        update.message.reply_text("Выберите действие из предложенных кнопок.")
        return STATE_CHOOSE

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    return STATE_FIO

def get_fio(update, context):
    fio = update.message.text.strip()
    fio_parts = fio.split()
    if len(fio_parts) >= 3:
        fio1 = " ".join(fio_parts[:2])
        fio2 = fio_parts[2]
    elif len(fio_parts) == 2:
        fio1 = fio_parts[0]
        fio2 = fio_parts[1]
    else:
        fio1 = fio
        fio2 = ""
    context.user_data["fio1"] = fio1
    context.user_data["fio2"] = fio2
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

def get_citydate(update, context):
    context.user_data["footer"] = update.message.text.strip()
    try:
        # Все данные должны быть уже в user_data, иначе ошибка на твоей стороне сценария!
        gender  = context.user_data.get("gender", "")
        fio1    = context.user_data.get("fio1", "")
        fio2    = context.user_data.get("fio2", "")
        body    = context.user_data.get("body", "")
        footer  = context.user_data.get("footer", "")

        # Открываем шаблон
        img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)
        # Шрифты
        font_gender = ImageFont.truetype(BOLD_FONT_PATH, 36) if os.path.exists(BOLD_FONT_PATH) else ImageFont.truetype(FONT_PATH, 36)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52) if os.path.exists(BOLD_FONT_PATH) else ImageFont.truetype(FONT_PATH, 52)
        font_body = ImageFont.truetype(FONT_PATH, 28)
        font_footer = ImageFont.truetype(FONT_PATH, 22)

        # ====== НАНЕСЕНИЕ ТЕКСТА ======
        draw.text(COORDS["gender"], gender, font=font_gender, fill="black")
        draw.text(COORDS["fio1"], fio1, font=font_fio, fill="black")
        draw.text(COORDS["fio2"], fio2, font=font_fio, fill="black")

        # Основной текст с переносом по ширине (максимум 800 px, перенос слов)
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            line = ""
            for word in words:
                test_line = line + (" " if line else "") + word
                if font.getsize(test_line)[0] <= max_width:
                    line = test_line
                else:
                    if line:
                        lines.append(line)
                    line = word
            if line:
                lines.append(line)
            return lines

        y_body = COORDS["body"][1]
        for line in wrap_text(body, font_body, 900):
            draw.text((COORDS["body"][0], y_body), line, font=font_body, fill="black")
            y_body += font_body.getsize(line)[1] + 8

        draw.text(COORDS["footer"], footer, font=font_footer, fill="black")

        out_stream = io.BytesIO()
        img.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")

    except Exception as e:
        logging.exception("Ошибка при создании письма")
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    # Вернуть пользователя к стартовому меню и скрыть клавиатуру
    update.message.reply_text("Выберите действие:", reply_markup=ReplyKeyboardMarkup(
        [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]], resize_keyboard=True
    ))
    return STATE_CHOOSE

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_CHOOSE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO:    [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY:   [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_citydate)]
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
