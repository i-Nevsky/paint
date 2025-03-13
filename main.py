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

# Пути к файлам (убедись, что папка static находится в корне проекта)
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
FONT_SIZE = 20  # уменьшенный шрифт (в 2 раза меньше прежнего)

print("Путь к изображению:", BASE_IMAGE_PATH)
print("Файл изображения существует?", os.path.exists(BASE_IMAGE_PATH))
print("Путь к шрифту:", FONT_PATH)
print("Файл шрифта существует?", os.path.exists(FONT_PATH))

# Состояния диалога
STATE_TEXT = 1
STATE_EXPERT = 2
STATE_TOPIC = 3
STATE_PHOTO = 4

# Начало диалога
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(f"Привет, {user_first_name}! Пожалуйста, отправь свой текст.")
    return STATE_TEXT

# Получение ответа на первый вопрос
def get_text(update, context):
    text = update.message.text
    context.user_data["text"] = text
    update.message.reply_text("Напишите фамилию и имя эксперта:")
    return STATE_EXPERT

# Получение ответа на второй вопрос
def get_expert(update, context):
    expert = update.message.text
    context.user_data["expert"] = expert
    update.message.reply_text("Напишите тему эфира:")
    return STATE_TOPIC

# Получение ответа на третий вопрос и нанесение текста на изображение
def get_topic(update, context):
    topic = update.message.text
    context.user_data["topic"] = topic
    try:
        # Открываем базовое изображение (PNG) и переводим в RGBA
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Получаем ответы пользователя
        text = context.user_data.get("text", "")
        expert = context.user_data.get("expert", "")
        topic = context.user_data.get("topic", "")
        
        # Наносим текст в заданные координаты:
        # Первый ответ (текст) – в (20,20)
        draw.text((20, 20), text, font=font, fill="white")
        # Фамилия и имя эксперта – в (20,100)
        draw.text((20, 100), expert, font=font, fill="white")
        # Тема эфира – в (20,180)
        draw.text((20, 180), topic, font=font, fill="white")
        
        # Сохраняем изображение с нанесённым текстом в context для дальнейшей обработки
        context.user_data["final_image"] = base_image.copy()
        
        update.message.reply_text(
            "Текст нанесён. Теперь отправьте фото, чтобы вставить его в круг справа, "
            "или введите /skip, чтобы использовать только изображение с текстом."
        )
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        return ConversationHandler.END

# Обработка фото от пользователя: наложение обрезанного по кругу фото на изображение
def get_photo(update, context):
    try:
        if update.message.photo:
            # Скачиваем фото пользователя
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            
            final_image = context.user_data.get("final_image")
            if not final_image:
                update.message.reply_text("Изображение с текстом не найдено.")
                return ConversationHandler.END
            
            final_image = final_image.convert("RGBA")
            
            # Определяем диаметр круга для фото (например, 230 пикселей)
            circle_diameter = 230
            user_photo = user_photo.resize((circle_diameter, circle_diameter), Image.ANTIALIAS)
            
            # Создаём маску для обрезки фото по кругу
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            
            # Рассчитываем позицию для вставки фото
            base_w, base_h = final_image.size
            # Пример: вставляем фото с правой стороны, отступ 50 пикселей от правого и 50 от верхнего края
            x_pos = base_w - circle_diameter - 50
            y_pos = 50
            
            final_image.paste(user_photo, (x_pos, y_pos), user_photo)
            
            # Преобразуем итоговое изображение в RGB и отправляем
            final_image_rgb = final_image.convert("RGB")
            out_stream = io.BytesIO()
            final_image_rgb.save(out_stream, format="JPEG")
            out_stream.seek(0)
            
            update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение с наложенным фото!")
            
            # Пытаемся удалить исходное сообщение с фото (если бот имеет права)
            try:
                bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
            except Exception as del_err:
                logging.error(f"Ошибка при удалении сообщения: {del_err}")
        else:
            update.message.reply_text("Пожалуйста, отправьте изображение.")
            return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
    return ConversationHandler.END

# Если пользователь вводит /skip – отправляем изображение без фото
def skip_photo(update, context):
    final_image = context.user_data.get("final_image")
    if final_image:
        final_image_rgb = final_image.convert("RGB")
        out_stream = io.BytesIO()
        final_image_rgb.save(out_stream, format="JPEG")
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
        STATE_EXPERT: [MessageHandler(Filters.text & ~Filters.command, get_expert)],
        STATE_TOPIC: [MessageHandler(Filters.text & ~Filters.command, get_topic)],
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
