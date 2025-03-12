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

# Состояния диалога
STATE_TEXT = 1
STATE_PHOTO = 2

# Обработчик команды /start – запрашивает текст
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(f"Привет, {user_first_name}! Пожалуйста, отправь свой текст.")
    return STATE_TEXT

# Обработчик получения текста и нанесения его на базовое изображение
def get_text(update, context):
    text = update.message.text
    try:
        # Открываем базовое изображение
        base_image = Image.open(BASE_IMAGE_PATH)
        draw = ImageDraw.Draw(base_image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Заменяем слово "привет" на имя пользователя (если встречается)
        user_first_name = update.message.from_user.first_name
        text = text.replace("привет", user_first_name)
        
        # Разбиваем текст на две строки (при наличии хотя бы двух слов)
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            final_text = parts[0] + "\n" + parts[1]
        else:
            final_text = text
        
        # Наносим текст в левом верхнем углу (координаты (20,20))
        text_position = (20, 20)
        draw.text(text_position, final_text, font=font, fill="white")
        
        # Сохраняем полученное изображение в контексте для дальнейшего использования
        context.user_data["final_image"] = base_image.copy()
        
        # Просим пользователя отправить фото для наложения или команду /skip
        update.message.reply_text("Твой текст нанесён. Теперь отправь своё фото, которое нужно наложить на это изображение, либо введи /skip, чтобы использовать только изображение с текстом.")
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        return ConversationHandler.END

# Обработчик получения фото от пользователя и наложения его на изображение с текстом
def get_photo(update, context):
    try:
        if update.message.photo:
            # Получаем фото (наиболее качественную версию)
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            
            # Берем ранее сохранённое изображение с текстом
            final_image = context.user_data.get("final_image")
            if not final_image:
                update.message.reply_text("Изображение с текстом не найдено.")
                return ConversationHandler.END
            
            # Приводим базовое изображение к режиму RGBA для корректного наложения
            final_image = final_image.convert("RGBA")
            
            # Задаём позицию для наложения фото (например, (100, 100))
            overlay_position = (100, 100)
            
            # Накладываем пользовательское фото (с учетом прозрачности, если есть)
            final_image.paste(user_photo, overlay_position, user_photo)
            
            # Преобразуем итоговое изображение в RGB (для JPEG)
            final_image = final_image.convert("RGB")
            out_stream = io.BytesIO()
            final_image.save(out_stream, format="JPEG")
            out_stream.seek(0)
            
            update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение с наложенным фото!")
        else:
            update.message.reply_text("Пожалуйста, отправьте фото.")
            return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
    return ConversationHandler.END

# Обработчик команды /skip – пользователь отказывается от наложения фото
def skip_photo(update, context):
    final_image = context.user_data.get("final_image")
    if final_image:
        final_image = final_image.convert("RGB")
        out_stream = io.BytesIO()
        final_image.save(out_stream, format="JPEG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение без дополнительного фото!")
    else:
        update.message.reply_text("Изображение не найдено.")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_TEXT: [MessageHandler(Filters.text & ~Filters.command, get_text)],
        STATE_PHOTO: [
            MessageHandler(Filters.photo, get_photo),
            CommandHandler('skip', skip_photo)
        ]
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
