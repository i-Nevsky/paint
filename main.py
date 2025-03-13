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
    Filters,
    CallbackQueryHandler
)
from telegram_bot_calendar import DetailedTelegramCalendar
from PIL import Image, ImageDraw, ImageFont

print("Current working directory:", os.getcwd())

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Установи переменную окружения TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам – убедись, что в папке static находятся base_image.png и roboto.ttf
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")

print("Путь к изображению:", BASE_IMAGE_PATH)
print("Файл изображения существует?", os.path.exists(BASE_IMAGE_PATH))
print("Путь к шрифту:", FONT_PATH)
print("Файл шрифта существует?", os.path.exists(FONT_PATH))

# Состояния диалога
STATE_DATE_TIME = 1
STATE_EXPERT = 2
STATE_TOPIC = 3
STATE_PHOTO = 4

# 1. Начало диалога: inline календарь для выбора даты
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(
        f"Привет, {user_first_name}! Пожалуйста, выберите дату:"
    )
    calendar, step = DetailedTelegramCalendar().build()
    update.message.reply_text("Выберите дату:", reply_markup=calendar)
    return STATE_DATE_TIME

# Callback для календаря
def calendar_callback(update, context):
    query = update.callback_query
    result, key, step = DetailedTelegramCalendar().process(query.data)
    if not result and key:
        query.edit_message_text(text=f"Выберите дату: {key}")
        query.edit_message_reply_markup(reply_markup=key)
        return STATE_DATE_TIME
    elif result:
        query.edit_message_text(text=f"Вы выбрали: {result}")
        # Фиксированное время – можно дополнительно спросить, но здесь задаём 13:00 МСК
        context.user_data["date_time_text"] = f"{result} 13:00 МСК"
        query.message.reply_text("Напишите фамилию и имя эксперта:")
        return STATE_EXPERT

# 2. Получение фамилии и имени эксперта
def get_expert(update, context):
    expert = update.message.text
    logging.info(f"Получено имя эксперта: {expert}")
    context.user_data["expert_text"] = expert
    update.message.reply_text("Напишите тему эфира:")
    return STATE_TOPIC

# 3. Получение темы эфира и нанесение текстов на изображение
def get_topic(update, context):
    topic = update.message.text
    context.user_data["topic_text"] = topic
    try:
        # Открываем базовое изображение (PNG) и переводим в RGBA
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        # Шрифты:
        # Дата/время – размер 25,
        # ФИО эксперта – размер 30,
        # Тема эфира – размер 30.
        font_dt = ImageFont.truetype(FONT_PATH, 45)
        font_expert = ImageFont.truetype(FONT_PATH, 70)
        font_topic = ImageFont.truetype(FONT_PATH, 70)
        
        dt_text = context.user_data.get("date_time_text", "")
        expert_text = context.user_data.get("expert_text", "")
        topic_text = context.user_data.get("topic_text", "")
        
        # Наносим тексты:
        # Дата и время в верхнем левом углу (20,20)
        draw.text((20, 20), dt_text, font=font_dt, fill="white")
        # Фамилия и имя эксперта – размещаем, например, в точке (20,150)
        draw.text((20, 150), expert_text, font=font_expert, fill="white")
        # Тема эфира – под экспертом, в точке (20,220)
        draw.text((20, 220), topic_text, font=font_topic, fill="white")
        
        # Сохраняем изображение с нанесёнными текстами для дальнейшей обработки фото
        context.user_data["final_image"] = base_image.copy()
        
        update.message.reply_text(
            "Тексты нанесены. Теперь отправьте фото, которое нужно вставить в круг справа, "
            "или введите /skip, чтобы использовать только изображение с текстами."
        )
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        return ConversationHandler.END

# 4. Получение фото: обрезка по кругу и вставка в заданную область (например, в красный кружок)
def get_photo(update, context):
    try:
        if update.message.photo:
            # Скачиваем фото пользователя (наиболее качественную версию)
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            
            # Получаем ранее сохранённое изображение с текстами
            final_image = context.user_data.get("final_image")
            if not final_image:
                update.message.reply_text("Изображение с текстами не найдено.")
                return ConversationHandler.END
            
            final_image = final_image.convert("RGBA")
            
            # Задаем диаметр круга для фото пользователя (например, 430 пикселей)
            circle_diameter = 430
            user_photo = user_photo.resize((circle_diameter, circle_diameter), Image.ANTIALIAS)
            
            # Создаем маску для обрезки по кругу
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            
            # Рассчитываем позицию для вставки фото в красный кружок.
            base_w, base_h = final_image.size
            # Пример: фото вставляется с отступом 80 пикселей от правого края и 120 от верхнего края.
            x_pos = base_w - circle_diameter - 90
            y_pos = 170
            
            final_image.paste(user_photo, (x_pos, y_pos), user_photo)
            
            # Преобразуем итоговое изображение в RGB (для сохранения в JPEG)
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
        STATE_DATE_TIME: [CallbackQueryHandler(calendar_callback)],
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
