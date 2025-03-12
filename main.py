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

# Вывод текущей рабочей директории для отладки
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

# Отладочный вывод для проверки наличия файлов
print("Путь к изображению:", BASE_IMAGE_PATH)
print("Файл изображения существует?", os.path.exists(BASE_IMAGE_PATH))
print("Путь к шрифту:", FONT_PATH)
print("Файл шрифта существует?", os.path.exists(FONT_PATH))

# Константа для состояния диалога
GET_DATE_TIME = 1

# Обработчик команды /start: добавляем имя пользователя в приветствие
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(f"Привет, {user_first_name}! Пожалуйста, отправь свой текст.")
    return GET_DATE_TIME

# Обработчик получения текста и наложения его на изображение
def get_date_time(update, context):
    text = update.message.text
    try:
        image = Image.open(BASE_IMAGE_PATH)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Если в тексте встречается слово "привет", заменяем его на имя пользователя
        user_first_name = update.message.from_user.first_name
        text = text.replace("привет", user_first_name)
        
        # Разбиваем текст на две строки, если возможно (при наличии хотя бы двух слов)
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            final_text = parts[0] + "\n" + parts[1]
        else:
            final_text = text
        
        # Фиксированная позиция в левом верхнем углу (20,20)
        position = (20, 20)
        
        # Накладываем текст на изображение
        draw.text(position, final_text, font=font, fill="white")
        
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

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        GET_DATE_TIME: [MessageHandler(Filters.text & ~Filters.command, get_date_time)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

dispatcher.add_handler(conv_handler)

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
