from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import aiohttp
import threading

# --- FastAPI часть ---

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import aiohttp

app = FastAPI()

class SearchRequest(BaseModel):
    user_id: int
    mood: str
    budget: str
    lat: float
    lon: float
    scope: str  # "nearby" or "city"

class Place(BaseModel):
    title: str
    url: str

class SearchResponse(BaseModel):
    results: List[Place]

@app.post("/search", response_model=SearchResponse)
async def search_places(request: SearchRequest):
    radius = 1000 if request.scope == "nearby" else 5000
    categories = ["cafe", "restaurant", "library", "spa", "park", "bowling_alley"]

    queries = "\n".join([
        f"node[\"amenity\"=\"{cat}\"](around:{radius},{request.lat},{request.lon});" for cat in categories
    ])

    overpass_query = f"""
    [out:json];
    (
        {queries}
    );
    out;
    """

    overpass_url = "https://overpass-api.de/api/interpreter"
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

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import threading

ASK_NAME, ASK_MOOD, ASK_BUDGET, ASK_SCOPE, ASK_LOCATION, SHOW_PLACES, MAIN_MENU = range(7)

user_data_store = {}

main_menu_keyboard = ReplyKeyboardMarkup([
    ["🎯 Новая подборка", "⭐ Избранное"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я FeelGo — твой навигатор по настроению и местам 🌟\nКак тебя зовут?")
    return ASK_NAME

async def ask_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id] = {
        "name": update.message.text,
        "favorites": []
    }
    await update.message.reply_text("Как ты себя чувствуешь?", reply_markup=ReplyKeyboardMarkup(
        [[m] for m in moods.keys()], resize_keyboard=True))
    return ASK_MOOD

async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id]["mood"] = update.message.text
    await update.message.reply_text("Какой у тебя бюджет?", reply_markup=ReplyKeyboardMarkup(
        [[b] for b in budgets.keys()], resize_keyboard=True))
    return ASK_BUDGET

async def ask_scope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id]["budget"] = update.message.text
    await update.message.reply_text("Где искать места?", reply_markup=ReplyKeyboardMarkup(
        [["📍 Поблизости", "🏙️ По всему городу"]], resize_keyboard=True))
    return ASK_SCOPE

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id]["scope"] = "nearby" if "Поблизости" in update.message.text else "city"
    await update.message.reply_text("📍 Отправь свою геолокацию:", reply_markup=ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Отправить локацию", request_location=True)]], resize_keyboard=True))
    return ASK_LOCATION

async def fetch_recommendations(user_id, mood, budget, lat, lon, scope):
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:8000/search", json={
            "user_id": user_id,
            "mood": mood,
            "budget": budget,
            "lat": lat,
            "lon": lon,
            "scope": scope
        }) as resp:
            return await resp.json()

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_data = user_data_store[user_id]

    await update.message.reply_text("⏳ Ищем места...")
    results = await fetch_recommendations(user_id, user_data["mood"], user_data["budget"], lat, lon, user_data["scope"])
    places = results.get("results", [])

    if not places:
        await update.message.reply_text("🙁 Ничего не найдено.")
        return MAIN_MENU

    user_data["recommendations"] = places

    for idx, place in enumerate(places):
        text = f"🏙 {place['title']}\n📍 {place['url']}"
        keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton("⭐ Добавить в избранное", callback_data=f"fav_{idx}"))
        await update.message.reply_text(text, reply_markup=keyboard)

    return MAIN_MENU

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    idx = int(query.data.split("_")[1])
    place = user_data_store[user_id]["recommendations"][idx]
    user_data_store[user_id]["favorites"].append(f"{place['title']}\n{place['url']}")
    await query.edit_message_reply_markup(None)
    await query.message.reply_text("⭐ Добавлено в избранное!", reply_markup=main_menu_keyboard)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⭐ Избранное":
        favorites = user_data_store[user_id].get("favorites", [])
        if favorites:
            await update.message.reply_text("\n\n".join(favorites))
        else:
            await update.message.reply_text("Список избранного пуст.")
        return MAIN_MENU

    elif text == "🎯 Новая подборка":
        await update.message.reply_text("Как ты себя чувствуешь?", reply_markup=ReplyKeyboardMarkup(
            [[m] for m in moods.keys()], resize_keyboard=True))
        return ASK_MOOD

    else:
        await update.message.reply_text("Пожалуйста, выбери действие из меню.")
        return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог завершён. Напиши /start, чтобы начать заново.")
    return ConversationHandler.END

# --- Словари состояний ---

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

# --- Запуск ---

def start_bot():
    TOKEN = "7800040116:AAGpWmzJoP79h2hA5q7VQNmDiI2jJCagKM8"
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_mood)],
            ASK_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_scope)],
            ASK_SCOPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
            ASK_LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    print("Telegram-бот запущен...")
    application.run_polling()

def run_fastapi():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    threading.Thread(target=run_fastapi, daemon=True).start()
    start_bot()


