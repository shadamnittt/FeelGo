from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import aiohttp
import threading

# --- FastAPI часть ---

app = FastAPI()

class SearchRequest(BaseModel):
    user_id: int
    mood: str
    budget: str
    lat: float
    lon: float

class Place(BaseModel):
    title: str
    url: str

class SearchResponse(BaseModel):
    results: List[Place]

moods = {
    "😔 Грусть": "Вот уютные места, где можно немного отвлечься и отдохнуть.",
    "😍 Радость": "Вот места, где ты сможешь зарядиться ещё больше!",
    "😠 Злость": "Вот активности, чтобы выпустить пар и отвлечься.",
    "🙂 Спокойствие": "Вот приятные и нейтральные локации для отдыха.",
    "🤯 Усталость": "Вот места, где можно перезагрузиться и восстановиться.",
    "🤩 Вдохновение": "Вот креативные пространства, чтобы зарядиться идеями."
}

budgets = {
    "💸 Эконом": "Бюджетный вариант.",
    "💰 Средний": "Хороший баланс между ценой и атмосферой.",
    "💎 Премиум": "Премиальные впечатления ждут тебя!"
}

@app.post("/search", response_model=SearchResponse)
async def search_places(request: SearchRequest):
    overpass_url = "https://overpass-api.de/api/interpreter"
    # Ищем кафе в радиусе 1000 метров от переданных координат
    overpass_query = f"""
    [out:json];
    node["amenity"="cafe"](around:1000,{request.lat},{request.lon});
    out;
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(overpass_url, data=overpass_query) as resp:
            data = await resp.json()

    places = []
    for element in data.get("elements", []):
        name = element.get("tags", {}).get("name", "Без названия")
        lat = element.get("lat")
        lon = element.get("lon")
        url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
        places.append({"title": name, "url": url})

    return SearchResponse(results=places)


# --- Telegram-бот часть ---

ASK_NAME, ASK_MOOD, ASK_BUDGET, MAIN_MENU, ASK_LOCATION = range(5)

user_data_store = {}

main_menu_keyboard = ReplyKeyboardMarkup(
    [["🎯 Новая подборка", "⭐ Избранное"]], resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я FeelGo — твой навигатор по настроению и местам 🌟\nКак тебя зовут?")
    return ASK_NAME

async def ask_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id] = {
        "name": update.message.text,
        "favorites": []
    }
    await update.message.reply_text(
        f"Рад познакомиться, {update.message.text}! 😊\nКак ты себя чувствуешь?",
        reply_markup=ReplyKeyboardMarkup([[m] for m in moods.keys()], resize_keyboard=True)
    )
    return ASK_MOOD

async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id]["mood"] = update.message.text
    await update.message.reply_text(
        "На какой бюджет ты рассчитываешь?",
        reply_markup=ReplyKeyboardMarkup([[b] for b in budgets.keys()], resize_keyboard=True)
    )
    return ASK_BUDGET

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store[user_id]["budget"] = update.message.text
    await update.message.reply_text(
        "🔍 Ищем подходящие места...\n📍 Отправь свою локацию, чтобы продолжить.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Отправить локацию", request_location=True)]],
            resize_keyboard=True
        )
    )
    return ASK_LOCATION

async def fetch_recommendations(user_id, mood, budget, lat, lon):
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:8000/search", json={
            "user_id": user_id,
            "mood": mood,
            "budget": budget,
            "lat": lat,
            "lon": lon
        }) as resp:
            return await resp.json()

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mood = user_data_store[user_id]["mood"]
    budget = user_data_store[user_id]["budget"]
    lat = update.message.location.latitude
    lon = update.message.location.longitude

    await update.message.reply_text("⏳ Подбираем лучшие варианты...")

    results = await fetch_recommendations(user_id, mood, budget, lat, lon)
    places = results.get("results", [])

    if not places:
        await update.message.reply_text("🙁 Ничего не найдено поблизости.")
    else:
        for place in places:
            title = place.get("title")
            url = place.get("url")
            await update.message.reply_text(f"🏙 {title}\n📍 {url}")

        user_data_store[user_id]["last_recommendation"] = f"{moods[mood]} {budgets[budget]}"

    await update.message.reply_text(
        "Хочешь добавить в избранное?",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Добавить в избранное", "🔙 Главное меню"]],
            resize_keyboard=True
        )
    )
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "✅ Добавить в избранное":
        last = user_data_store[user_id].get("last_recommendation")
        if last:
            user_data_store[user_id]["favorites"].append(last)
            await update.message.reply_text("Добавлено в избранное! ⭐", reply_markup=main_menu_keyboard)
        else:
            await update.message.reply_text("Нет данных для добавления.")
        return MAIN_MENU

    elif text == "⭐ Избранное":
        favorites = user_data_store[user_id].get("favorites", [])
        if favorites:
            await update.message.reply_text("\n\n".join(favorites), reply_markup=main_menu_keyboard)
        else:
            await update.message.reply_text("Пока что список избранного пуст.", reply_markup=main_menu_keyboard)
        return MAIN_MENU

    elif text == "🎯 Новая подборка":
        await update.message.reply_text(
            "Как ты себя чувствуешь?",
            reply_markup=ReplyKeyboardMarkup(
                [[m] for m in moods.keys()], resize_keyboard=True)
        )
        return ASK_MOOD

    else:
        await update.message.reply_text("Пожалуйста, выбери действие из меню.")
        return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог завершён. Напиши /start, чтобы начать заново.")
    return ConversationHandler.END

def start_bot():
    TOKEN = "7800040116:AAGpWmzJoP79h2hA5q7VQNmDiI2jJCagKM8"
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_mood)],
            ASK_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
            ASK_LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    print("Telegram-бот запущен...")
    application.run_polling()

# --- Запуск FastAPI и Telegram бота параллельно ---

def run_fastapi():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # Запускаем FastAPI сервер в отдельном потоке
    threading.Thread(target=run_fastapi, daemon=True).start()
    # Запускаем Telegram-бота в основном потоке
    start_bot()

