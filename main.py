import logging
import os
import io
import re
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
STATE_DATE_INPUT = 1
STATE_EXPERT = 2
STATE_TOPIC = 3
STATE_PHOTO = 4

# Функция для переноса строки, если текст выходит за пределы max_width
def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        w, _ = font.getsize(test_line)
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

# Функция для разделения даты и времени.
def split_date_time(dt_text):
    tokens = dt_text.split()
    for i, token in enumerate(tokens):
        if re.search(r'\d{1,2}:\d{2}', token):
            date_part = " ".join(tokens[:i])
            time_part = " ".join(tokens[i:])
            return date_part, time_part
    return dt_text, ""

# 1. Начало диалога: запрос даты и времени ввода вручную
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(
        f"Привет, {user_first_name}! Введи дату и время (например, 14 марта 13:00 МСК):"
    )
    return STATE_DATE_INPUT

# Получение даты и времени
def get_date_time(update, context):
    date_time_text = update.message.text
    context.user_data["date_time_text"] = date_time_text
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return STATE_EXPERT

# 2. Получение ФИО эксперта с автоматическим уменьшением шрифта при превышении ширины
def get_expert(update, context):
    expert = update.message.text
    logging.info(f"Получено имя эксперта: {expert}")
    context.user_data["expert_text"] = expert
    update.message.reply_text("Напиши тему эфира:")
    return STATE_TOPIC

# 3. Получение темы эфира и нанесение текстов на изображение
def get_topic(update, context):
    topic = update.message.text
    context.user_data["topic_text"] = topic
    try:
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        # Определяем шрифты:
        # Дата/время – размер 45.
        font_dt = ImageFont.truetype(FONT_PATH, 45)
        # Для ФИО эксперта – начальный размер 70.
        expert_font_size = 70
        font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
        # Тема эфира – размер 70 (с дальнейшей регулировкой по высоте).
        topic_font_size = 70
        font_topic = ImageFont.truetype(FONT_PATH, topic_font_size)
        
        dt_text = context.user_data.get("date_time_text", "")
        expert_text = context.user_data.get("expert_text", "")
        topic_text = context.user_data.get("topic_text", "")
        
        # Разбиваем дату и время: отделяем время, если найдено (например, 13:00)
        dt_date, dt_time = split_date_time(dt_text)
        y_offset = 20
        if dt_date:
            draw.text((20, y_offset), dt_date, font=font_dt, fill="white")
            y_offset += font_dt.getsize(dt_date)[1] + 5
        if dt_time:
            draw.text((20, y_offset), dt_time, font=font_dt, fill="white")
            y_offset += font_dt.getsize(dt_time)[1] + 5
        
        # Уменьшаем шрифт для ФИО эксперта, если текст выходит за пределы x=570 (доступная ширина 550 пикселей)
        max_expert_width = 550
        expert_text_width, _ = font_expert.getsize(expert_text)
        while expert_text_width > max_expert_width and expert_font_size > 30:
            expert_font_size -= 5
            font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
            expert_text_width, _ = font_expert.getsize(expert_text)
        # Рисуем ФИО эксперта (фиксированно, например, в точке (20,380))
        draw.text((20, 370), expert_text, font=font_expert, fill="white")
        
        # Рисуем тему эфира с переносом строк, если текст выходит за координату x=570.
        topic_start_y = 450
        max_topic_y = 570
        available_height = max_topic_y - topic_start_y
        max_width = 550  # доступная ширина от x=20 до x=570
        
        topic_lines = wrap_text(topic_text, font_topic, max_width)
        total_height = sum(font_topic.getsize(line)[1] for line in topic_lines) + (len(topic_lines)-1)*5
        
        # Если текст не умещается по высоте, уменьшаем шрифт до тех пор, пока не поместится
        while total_height > available_height and topic_font_size > 10:
            topic_font_size -= 5
            font_topic = ImageFont.truetype(FONT_PATH, topic_font_size)
            topic_lines = wrap_text(topic_text, font_topic, max_width)
            total_height = sum(font_topic.getsize(line)[1] for line in topic_lines) + (len(topic_lines)-1)*5
        
        y_offset_topic = topic_start_y
        for line in topic_lines:
            draw.text((20, y_offset_topic), line, font=font_topic, fill="white")
            y_offset_topic += font_topic.getsize(line)[1] + 5
        
        context.user_data["final_image"] = base_image.copy()
        
        update.message.reply_text(
            "Тексты нанесены. Теперь отправь фото, которое нужно вставить в заданную область, "
            "или введи /skip, чтобы использовать только изображение с текстами."
        )
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        return ConversationHandler.END

# 4. Получение фото: обрезка по кругу и вставка в заданную область с прозрачным фоном,
# при этом картинку пользователя подгоняем с сохранением пропорций.
def get_photo(update, context):
    try:
        if update.message.photo:
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            
            final_image = context.user_data.get("final_image")
            if not final_image:
                update.message.reply_text("Изображение с текстами не найдено.")
                return ConversationHandler.END
            
            final_image = final_image.convert("RGBA")
            
            circle_diameter = 480
            # Используем ImageOps.fit для обрезки по центру с сохранением пропорций
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS)
            
            # Создаём маску для круглой обрезки
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            
            base_w, base_h = final_image.size
            x_pos = base_w - circle_diameter - 70
            y_pos = 235
            
            # Создаём временный слой с прозрачным фоном и вставляем на него фото
            temp_layer = Image.new("RGBA", (circle_diameter, circle_diameter), (0, 0, 0, 0))
            temp_layer.paste(user_photo, (0, 0), user_photo)
            final_image.alpha_composite(temp_layer, (x_pos, y_pos))
            
            final_image_rgb = final_image.convert("RGB")
            out_stream = io.BytesIO()
            final_image_rgb.save(out_stream, format="JPEG")
            out_stream.seek(0)
            
            update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение с наложенным фото!")
            
            try:
                bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
            except Exception as del_err:
                logging.error(f"Ошибка при удалении сообщения: {del_err}")
        else:
            update.message.reply_text("Пожалуйста, отправь изображение.")
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
        STATE_DATE_INPUT: [MessageHandler(Filters.text & ~Filters.command, get_date_time)],
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

# Для некоторых хостингов может потребоваться:
application = app
