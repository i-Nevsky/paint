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
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image_grid.jpeg")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto-bold.ttf")

COORDS = {
    "gender":  (650, 450),    # «Уважаемый»
    "name":    (650, 550),    # Имя + Отчество
    "surname": (650, 650),    # Фамилия
    "body":    (350, 750),    # Основной текст
    "footer":  (650, 1350),   # Город и дата
}

# Состояния
STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"]]
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

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text(
        "Введите ФИО:",
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_BODY

def get_fio(update, context):
    fio = update.message.text.strip()
    fio_parts = fio.split()
    if len(fio_parts) == 3:
        context.user_data["name"] = fio_parts[0] + " " + fio_parts[1]
        context.user_data["surname"] = fio_parts[2]
    else:
        context.user_data["name"] = fio
        context.user_data["surname"] = ""
    update.message.reply_text("Введите основной текст благодарности:")
    return STATE_CITYDATE

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return ConversationHandler.END

def get_citydate(update, context):
    context.user_data["footer"] = update.message.text.strip()
    try:
        # Открываем шаблон письма
        img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Шрифты
        f_gen    = ImageFont.truetype(FONT_PATH,      50)
        f_name   = ImageFont.truetype(BOLD_FONT_PATH, 56)
        f_surname= ImageFont.truetype(BOLD_FONT_PATH, 72)
        f_body   = ImageFont.truetype(FONT_PATH,      34)
        f_footer = ImageFont.truetype(FONT_PATH,      32)

        # Вставляем текст
        draw.text(COORDS["gender"],  context.user_data["gender"],  font=f_gen,    fill="black", anchor="mm")
        draw.text(COORDS["name"],    context.user_data["name"],    font=f_name,   fill="black", anchor="mm")
        draw.text(COORDS["surname"], context.user_data["surname"], font=f_surname,fill="black", anchor="mm")
        draw.multiline_text(COORDS["body"], context.user_data["body"], font=f_body, fill="black", spacing=8, anchor="lm")
        draw.text(COORDS["footer"], context.user_data["footer"], font=f_footer, fill="black", anchor="mm")

        # Сохраняем в память
        out_stream = io.BytesIO()
        img.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_FIO:    [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_BODY:   [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_CITYDATE:[MessageHandler(Filters.text & ~Filters.command, get_body)],
        ConversationHandler.END: [MessageHandler(Filters.text & ~Filters.command, get_citydate)],
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
