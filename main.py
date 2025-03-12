import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont

print("Current working directory:", os.getcwd())

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Установи переменную окружения TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.jpg")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
FONT_SIZE = 40

print("Путь к изображению:", BASE_IMAGE_PATH)
print("Файл изображения существует?", os.path.exists(BASE_IMAGE_PATH))
print("Путь к шрифту:", FONT_PATH)
print("Файл шрифта существует?", os.path.exists(FONT_PATH))

# Константы состояний для диалогов
GET_DATE_TIME = 1
GET_OVERLAY_IMAGE = 2

# Диалог для наложения текста на базовую картинку (команда /start)
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(f"Привет, {user_first_name}! Пожалуйста, отправь текст с датой и временем.")
    return GET_DATE_TIME

def get_date_time(update, context):
    text = update.message.text
    try:
        image = Image.open(BASE_IMAGE_PATH)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        user_first_name = update.message.from_user.first_name
        # Заменяем слово "привет" на имя пользователя, если оно встречается
        text = text.replace("привет", user_first_name)
        # Разбиваем текст на две строки (если возможно)
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            final_text = parts[0] + "\n" + parts[1]
        else:
            final_text = text
        # Фиксированная позиция в левом верхнем углу (20,20)
        position = (20, 20)
        draw.text(position, final_text, font=font, fill="white")
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="JPEG")
        img_byte_arr.seek(0)
        update.message.reply_photo(photo=img_byte_arr, caption="Вот изображение с твоим текстом!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
    return ConversationHandler.END

# Диалог для наложения изображения, отправленного пользователем, на базовую картинку (команда /overlayimg)
def overlay_image_start(update, context):
    update.message.reply_text("Пожалуйста, отправь изображение, которое нужно наложить на базовую картинку.")
    return GET_OVERLAY_IMAGE

def get_overlay_image(update, context):
    try:
        if update.message.photo:
            # Берем наиболее качественную версию изображения
            photo_file = update.message.photo[-1].get_file()
            overlay_stream = io.BytesIO()
            photo_file.download(out=overlay_stream)
            overlay_stream.seek(0)
            overlay_img = Image.open(overlay_stream).convert("RGBA")
            
            # Открываем базовую картинку и переводим её в режим RGBA для работы с прозрачностью
            base_img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
            
            # Задаем позицию для наложения изображения (например, (100,100))
            position = (100, 100)
            
            # Накладываем изображение с использованием альфа-канала (если есть)
            base_img.paste(overlay_img, position, overlay_img)
            
            # Преобразуем итоговое изображение в RGB для сохранения в JPEG
            final_image = base_img.convert("RGB")
            out_stream = io.BytesIO()
            final_image.save(out_stream, format="JPEG")
            out_stream.seek(0)
            update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение!")
        else:
            update.message.reply_text("Пожалуйста, отправьте изображение.")
            return GET_OVERLAY_IMAGE
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

# ConversationHandler для команды /start (наложение текста)
conv_handler_text = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        GET_DATE_TIME: [MessageHandler(Filters.text & ~Filters.command, get_date_time)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)
dispatcher.add_handler(conv_handler_text)

# ConversationHandler для команды /overlayimg (наложение изображения)
conv_handler_image = ConversationHandler(
    entry_points=[CommandHandler('overlayimg', overlay_image_start)],
    states={
        GET_OVERLAY_IMAGE: [MessageHandler(Filters.photo, get_overlay_image)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)
dispatcher.add_handler(conv_handler_image)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Получен апдейт: {data}")
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
