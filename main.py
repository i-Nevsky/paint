import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from PIL import Image, ImageDraw, ImageFont

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация Flask и Telegram Bot
app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Установи переменную окружения TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Путь к базовой картинке и файлу шрифта
BASE_IMAGE_PATH = "static/base_image.jpg"  # размести картинку в папке static
FONT_PATH = "static/font.ttf"              # размести шрифт в папке static
FONT_SIZE = 40

def start(update, context):
    update.message.reply_text("Привет! Используй команду /overlay <текст> для наложения текста на картинку.")

def overlay(update, context):
    text = ' '.join(context.args)
    if not text:
        update.message.reply_text("Укажи текст после команды, например: /overlay Привет мир!")
        return
    try:
        # Открываем картинку и подготавливаем объект для рисования
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
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        update.message.reply_photo(photo=img_byte_arr)
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")

# Регистрируем обработчики команд
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("overlay", overlay))

# Эндпоинт для приёма обновлений от Telegram через вебхук
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Получен апдейт: {data}")
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

# Добавляем обработчик для корневого URL
@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
