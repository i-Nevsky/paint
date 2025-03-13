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
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
FONT_SIZE = 20  # Уменьшенный шрифт (в 2 раза меньше прежнего)

print("Путь к изображению:", BASE_IMAGE_PATH)
print("Файл изображения существует?", os.path.exists(BASE_IMAGE_PATH))
print("Путь к шрифту:", FONT_PATH)
print("Файл шрифта существует?", os.path.exists(FONT_PATH))

# Состояния диалога
STATE_TEXT = 1
STATE_PHOTO = 2

def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(f"Привет, {user_first_name}! Пожалуйста, отправь свой текст.")
    return STATE_TEXT

def get_text(update, context):
    text = update.message.text
    try:
        # Открываем базовое изображение (PNG) и переводим в RGBA для прозрачности
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Заменяем слово "привет" на имя пользователя (если встречается)
        user_first_name = update.message.from_user.first_name
        text = text.replace("привет", user_first_name)
        
        # Разбиваем текст на две строки (если возможно)
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            final_text = parts[0] + "\n" + parts[1]
        else:
            final_text = text
        
        # Координаты для текста: верхний левый угол (20,20)
        text_position = (20, 20)
        
        # Рисуем текст белым цветом
        draw.text(text_position, final_text, font=font, fill="white")
        
        # Сохраняем полученное изображение в user_data для дальнейшего использования
        context.user_data["final_image"] = base_image.copy()
        
        update.message.reply_text(
            "Твой текст нанесён. Отправь фото, чтобы вставить его в круг справа, "
            "или введи /skip, чтобы пропустить."
        )
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        return ConversationHandler.END

def get_photo(update, context):
    try:
        if update.message.photo:
            # Скачиваем фото, которое прислал пользователь
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            
            # Берём ранее сохранённое изображение с текстом
            final_image = context.user_data.get("final_image")
            if not final_image:
                update.message.reply_text("Изображение с текстом не найдено.")
                return ConversationHandler.END
            
            final_image = final_image.convert("RGBA")
            
            # Диаметр круга для фото пользователя
            circle_diameter = 230
            user_photo = user_photo.resize((circle_diameter, circle_diameter), Image.ANTIALIAS)
            
            # Создаём маску для обрезки по кругу
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            
            # Рассчитываем позицию для вставки фото (правый верхний угол, с отступами)
            base_w, base_h = final_image.size
            x_pos = base_w - circle_diameter - 150  # смещение от правого края
            y_pos = 150  # смещение от верхнего края
            
            final_image.paste(user_photo, (x_pos, y_pos), user_photo)
            
            # Преобразуем итоговое изображение в RGB (для сохранения в JPEG)
            final_image_rgb = final_image.convert("RGB")
            out_stream = io.BytesIO()
            final_image_rgb.save(out_stream, format="JPEG")
            out_stream.seek(0)
            
            update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение с твоим фото в круге!")
            
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
