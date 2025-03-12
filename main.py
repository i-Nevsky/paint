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

# Далее остальной код...

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация Flask и Telegram Bot
app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Установи переменную окружения TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам и настройки для изображения
BASE_IMAGE_PATH = "static/base_image.jpg"  # размести картинку в папке static
FONT_PATH = "static/roboto.ttf"              # размести шрифт в папке static
FONT_SIZE = 40

# Константы для состояний диалога
GET_DATE_TIME = 1

# Обработчик команды /start, запускающий диалог
def start(update, context):
    update.message.reply_text("Привет! Пожалуйста, отправь текст с датой и временем.")
    return GET_DATE_TIME

# Обработчик получения текста от пользователя с датой и временем
# и наложение его на изображение
def get_date_time(update, context):
    text = update.message.text
    try:
        image = Image.open(BASE_IMAGE_PATH)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Вычисляем позицию для центрирования текста
        width, height = image.size
        text_width, text_height = draw.textsize(text, font=font)
        position = ((width - text_width) / 2, (height - text_height) / 2)
        
        # Накладываем текст на изображение
        draw.text(position, text, font=font, fill="white")
        
        # Сохраняем изображение в буфер
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="JPEG")
        img_byte_arr.seek(0)
        
        update.message.reply_photo(photo=img_byte_arr, caption="Вот изображение с твоим текстом!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

# ConversationHandler для /start
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        GET_DATE_TIME: [MessageHandler(Filters.text & ~Filters.command, get_date_time)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

dispatcher.add_handler(conv_handler)

# Эндпоинт для приёма обновлений от Telegram через вебхук
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Получен апдейт: {data}")
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

# Обработчик для корневого URL
@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
