
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

ASK_NAME, ASK_MOOD, ASK_BUDGET, MAIN_MENU = range(4)

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
    await update.message.reply_text(f"Рад познакомиться, {update.message.text}! 😊\nКак ты себя чувствуешь?",
                                    reply_markup=ReplyKeyboardMarkup([[m] for m in moods.keys()], resize_keyboard=True))
    return ASK_MOOD

async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id]["mood"] = update.message.text
    await update.message.reply_text("На какой бюджет ты рассчитываешь?",
                                    reply_markup=ReplyKeyboardMarkup([[b] for b in budgets.keys()], resize_keyboard=True))
    return ASK_BUDGET

async def show_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mood = user_data_store[user_id]["mood"]
    budget = update.message.text
    name = user_data_store[user_id]["name"]
    recommendation = f"{moods[mood]} {budgets[budget]}"
    user_data_store[user_id]["last_recommendation"] = recommendation
    await update.message.reply_text(
        f"{name}, ты выбрал настроение '{mood}' и бюджет '{budget}'.\n{recommendation}"
    )
    await update.message.reply_text("Хочешь добавить это в избранное?",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [["✅ Добавить в избранное", "🔙 Главное меню"]],
                                        resize_keyboard=True))
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
        await update.message.reply_text("Как ты себя чувствуешь?",
                                        reply_markup=ReplyKeyboardMarkup(
                                            [[m] for m in moods.keys()], resize_keyboard=True))
        return ASK_MOOD

    else:
        await update.message.reply_text("Пожалуйста, выбери действие из меню.")
        return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог завершён. Напиши /start, чтобы начать заново.")
    return ConversationHandler.END

def main():
    TOKEN = "7800040116:AAGpWmzJoP79h2hA5q7VQNmDiI2jJCagKM8"
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_mood)],
            ASK_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_recommendation)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()

