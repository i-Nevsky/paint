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

# ==== Пути к файлам ====
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.jpg")  # твой шаблон без сетки!
FONT_PATH = os.path.join(os.getcwd(), "static", "Times New Roman.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Times New Roman Bold.ttf")

# ==== Координаты (строго по твоей сетке) ====
COORDS = {
    "gender":  (510, 330),
    "name":    (350, 410),
    "surname": (300, 470),
    "body":    (170, 540),
    "footer":  (820, 970)
}

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
    else:
        update.message.reply_text("Пока реализован только шаблон благодарственного письма.")
        return ConversationHandler.END

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО полностью (Имя Отчество Фамилия):", reply_markup=ReplyKeyboardRemove())
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
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_CITYDATE

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return ConversationHandler.END

def get_citydate(update, context):
    context.user_data["footer"] = update.message.text.strip()
    try:
        # Открываем шаблон
        img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)
        f_gender  = ImageFont.truetype(FONT_PATH, 36)
        f_name    = ImageFont.truetype(BOLD_FONT_PATH, 44)
        f_surname = ImageFont.truetype(BOLD_FONT_PATH, 60)
        f_body    = ImageFont.truetype(FONT_PATH, 26)
        f_footer  = ImageFont.truetype(FONT_PATH, 22)
        
        # Тексты
        gender  = context.user_data.get("gender", "")
        name    = context.user_data.get("name", "")
        surname = context.user_data.get("surname", "")
        body    = context.user_data.get("body", "")
        footer  = context.user_data.get("footer", "")

        # Отрисовка текста
        draw.text(COORDS["gender"],  gender,  font=f_gender,  fill="black")
        draw.text(COORDS["name"],    name,    font=f_name,    fill="black")
        draw.text(COORDS["surname"], surname, font=f_surname, fill="black")

        # Многострочный основной текст
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            line = ""
            for word in words:
                test_line = f"{line} {word}".strip()
                if font.getsize(test_line)[0] <= max_width:
                    line = test_line
                else:
                    if line:
                        lines.append(line)
                    line = word
            if line:
                lines.append(line)
            return lines
        
        body_lines = wrap_text(body, f_body, 900)
        y_offset = COORDS["body"][1]
        for line in body_lines:
            draw.text((COORDS["body"][0], y_offset), line, font=f_body, fill="black")
            y_offset += f_body.getsize(line)[1] + 5

        draw.text(COORDS["footer"], footer, font=f_footer, fill="black")
        
        # Сохраняем и отправляем
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
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        ConversationHandler.END: [MessageHandler(Filters.text & ~Filters.command, get_citydate)]
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
