from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import BaseMiddleware
from aiogram.types import Update, Message
import asyncio
import logging
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN не найден. Бот не запустится.")
    exit(1)

from database import init_db, save_user, get_user, add_log, get_today_stats, clear_user_logs
from utils import get_weather, get_calories, calculate_goals, calculate_burned_calories

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

user_state = {}

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        try:
            if isinstance(event, Update) and event.message:
                user = event.message.from_user
                user_id = user.id
                username = user.username or "без username"
                first_name = user.first_name or ""
                last_name = user.last_name or ""
                full_name = f"{first_name} {last_name}".strip()
                
                text = event.message.text or ""
                chat_id = event.message.chat.id
                
                logger.info(
                    f"📨 Сообщение от пользователя: "
                    f"ID={user_id}, "
                    f"Username=@{username}, "
                    f"Имя='{full_name}', "
                    f"Чат ID={chat_id}, "
                    f"Текст='{text}'"
                )
                
                if text.startswith('/'):
                    logger.info(f"🚀 Команда: {text}")
            
            elif isinstance(event, Update) and event.callback_query:
                user = event.callback_query.from_user
                user_id = user.id
                data_text = event.callback_query.data or ""
                
                logger.info(f"🔄 Callback от пользователя {user_id}: {data_text}")
        
        except Exception as e:
            logger.error(f"Ошибка в middleware: {e}")
        
        return await handler(event, data)

dp.update.middleware(LoggingMiddleware())

@dp.message(Command("start"))
async def start(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} начал работу с ботом")
    await message.answer(
        "🤖 Бот для контроля здоровья\n\n"
        "📋 Команды:\n"
        "/profile - мой профиль\n"
        "/setprofile - создать профиль\n"
        "/water 500 - записать воду\n"
        "/food яблоко 200 - записать еду\n"
        "/workout бег 30 - записать тренировку\n"
        "/progress - прогресс за сегодня\n"
        "/tips - рекомендации\n"
        "/reset - сбросить мои данные\n"
        "/help - помощь по командам"
    )

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} запросил помощь")
    await message.answer(
        "❓ Помощь по командам:\n\n"
        "💧 /water 500 - запишите количество воды в мл\n"
        "🍎 /food яблоко 200 - запишите еду (название и граммы)\n"
        "🏃 /workout бег 30 - запишите тренировку (тип и минуты)\n"
        "📊 /progress - посмотрите свой прогресс\n"
        "💡 /tips - персонализированные рекомендации\n"
        "👤 /profile - информация о профиле\n"
        "🔄 /reset - сбросить все данные"
    )

@dp.message(Command("reset"))
async def reset_cmd(message: types.Message):
    uid = message.from_user.id
    logger.info(f"Пользователь {uid} сбросил данные")
    clear_user_logs(uid)
    await message.answer("✅ Ваши данные сброшены. Создайте новый профиль: /setprofile")

@dp.message(Command("profile"))
async def show_profile(message: types.Message):
    uid = message.from_user.id
    logger.info(f"Пользователь {uid} запросил профиль")
    user = get_user(uid)
    
    if not user:
        await message.answer("❌ Сначала создайте профиль: /setprofile")
        return
    
    temp = get_weather(user['city'])
    
    await message.answer(
        f"👤 Ваш профиль:\n\n"
        f"📏 Антропометрия:\n"
        f"• Вес: {user['weight']} кг\n"
        f"• Рост: {user['height']} см\n"
        f"• Возраст: {user['age']} лет\n"
        f"• Активность: {user['activity']} мин/день\n\n"
        f"📍 Локация:\n"
        f"• Город: {user['city']}\n"
        f"• Температура: {temp:.1f}°C\n\n"
        f"🎯 Дневные цели:\n"
        f"• Вода: {user['water_goal']} мл\n"
        f"• Калории: {user['calorie_goal']} ккал"
    )

@dp.message(Command("setprofile"))
async def start_profile(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} начал создание профиля")
    
    clear_user_logs(user_id)
    
    user_state[user_id] = {'step': 'weight'}
    await message.answer("📝 Создание профиля\n\nШаг 1 из 5: Введите ваш вес (кг):")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]['step'] == 'weight')
async def process_weight(message: types.Message):
    try:
        weight = float(message.text)
        uid = message.from_user.id
        user_state[uid]['weight'] = weight
        user_state[uid]['step'] = 'height'
        logger.info(f"Пользователь {uid} указал вес: {weight} кг")
        await message.answer(f"✅ Вес: {weight} кг\n\nШаг 2 из 5: Введите ваш рост (см):")
    except:
        await message.answer("❌ Введите число (кг)\nПример: 70")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]['step'] == 'height')
async def process_height(message: types.Message):
    try:
        height = float(message.text)
        uid = message.from_user.id
        user_state[uid]['height'] = height
        user_state[uid]['step'] = 'age'
        logger.info(f"Пользователь {uid} указал рост: {height} см")
        await message.answer(f"✅ Рост: {height} см\n\nШаг 3 из 5: Введите ваш возраст (лет):")
    except:
        await message.answer("❌ Введите число (см)\nПример: 175")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]['step'] == 'age')
async def process_age(message: types.Message):
    try:
        age = int(message.text)
        uid = message.from_user.id
        user_state[uid]['age'] = age
        user_state[uid]['step'] = 'activity'
        logger.info(f"Пользователь {uid} указал возраст: {age} лет")
        await message.answer(
            f"✅ Возраст: {age} лет\n\n"
            f"Шаг 4 из 5: Введите вашу ежедневную активность (мин/день):\n\n"
            f"Примеры:\n"
            f"• 30 - минимальная активность\n"
            f"• 60 - умеренная активность\n"
            f"• 90 - высокая активность"
        )
    except:
        await message.answer("❌ Введите целое число (лет)\nПример: 25")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]['step'] == 'activity')
async def process_activity(message: types.Message):
    try:
        activity = int(message.text)
        uid = message.from_user.id
        user_state[uid]['activity'] = activity
        user_state[uid]['step'] = 'city'
        logger.info(f"Пользователь {uid} указал активность: {activity} мин/день")
        await message.answer(
            f"✅ Активность: {activity} мин/день\n\n"
            f"Шаг 5 из 5: Введите ваш город:\n\n"
            f"Примеры:\n"
            f"• Москва\n"
            f"• Санкт-Петербург\n"
            f"• Казань\n\n"
            f"Город нужен для учета погоды в расчетах"
        )
    except:
        await message.answer("❌ Введите число (минут)\nПример: 60")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]['step'] == 'city')
async def process_city(message: types.Message):
    city = message.text.strip()
    uid = message.from_user.id
    
    if not city or len(city) < 2:
        await message.answer("❌ Введите название города\nПример: Москва")
        return
    
    try:
        weight = user_state[uid]['weight']
        height = user_state[uid]['height']
        age = user_state[uid]['age']
        activity = user_state[uid]['activity']
        
        temp = get_weather(city)
        water_goal, calorie_goal = calculate_goals(weight, height, age, activity, temp)
        
        save_user(uid, 
                 weight=weight, height=height, age=age,
                 activity=activity, city=city,
                 water_goal=water_goal, calorie_goal=calorie_goal)
        
        logger.info(f"Пользователь {uid} создал профиль: "
                   f"вес={weight}кг, рост={height}см, возраст={age}лет, "
                   f"активность={activity}мин, город={city}, "
                   f"вода={water_goal}мл, калории={calorie_goal}ккал")
        
        del user_state[uid]
        
        await message.answer(
            f"✅ Профиль создан!\n\n"
            f"📊 Ваши параметры:\n"
            f"• Вес: {weight} кг\n"
            f"• Рост: {height} см\n"
            f"• Возраст: {age} лет\n"
            f"• Активность: {activity} мин/день\n"
            f"• Город: {city}\n"
            f"• Температура: {temp:.1f}°C\n\n"
            f"🎯 Ваши дневные цели:\n"
            f"💧 Вода: {water_goal} мл\n"
            f"🔥 Калории: {calorie_goal} ккал\n\n"
            f"📝 Теперь используйте команды:\n"
            f"• /water 500 - записать воду\n"
            f"• /food яблоко 200 - записать еду\n"
            f"• /workout бег 30 - записать тренировку\n"
            f"• /progress - посмотреть прогресс\n"
            f"• /tips - получить рекомендации"
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания профиля для пользователя {uid}: {e}")
        await message.answer(f"❌ Ошибка: {e}")
        if uid in user_state:
            del user_state[uid]

@dp.message()
async def handle_all_messages(message: types.Message):
    text = message.text or ""
    uid = message.from_user.id
    
    if uid in user_state:
        if user_state[uid]['step'] == 'weight':
            await process_weight(message)
        elif user_state[uid]['step'] == 'height':
            await process_height(message)
        elif user_state[uid]['step'] == 'age':
            await process_age(message)
        elif user_state[uid]['step'] == 'activity':
            await process_activity(message)
        elif user_state[uid]['step'] == 'city':
            await process_city(message)
        return
    
    if text.startswith('/'):
        try:
            parts = text.split()
            if not parts:
                await message.answer("❌ Неизвестная команда")
                return
                
            command = parts[0].lower()
            
            if command == '/water':
                if len(parts) >= 2:
                    try:
                        amount = int(parts[1])
                        user = get_user(uid)
                        
                        if not user:
                            await message.answer("❌ Сначала создайте профиль: /setprofile")
                            return
                        
                        if amount <= 0:
                            await message.answer("❌ Введите положительное число")
                            return
                        
                        add_log(uid, 'water', 'вода', amount)
                        logger.info(f"Пользователь {uid} записал воду: {amount} мл")
                        
                        stats = get_today_stats(uid)
                        
                        progress = min(100, int(stats['total_water'] / user['water_goal'] * 100))
                        bar = '█' * int(progress / 10) + '░' * (10 - int(progress / 10))
                        
                        await message.answer(
                            f"✅ Записано: {amount} мл воды\n"
                            f"💧 Всего сегодня: {stats['total_water']}/{user['water_goal']} мл\n"
                            f"{bar} {progress}%"
                        )
                    except ValueError:
                        await message.answer("❌ Введите число после /water\nПример: /water 500")
                else:
                    await message.answer("❌ Используйте: /water 500\nПример: /water 300")
                    
            elif command == '/food':
                if len(parts) >= 2:
                    try:
                        food_name = parts[1]
                        grams = 100
                        
                        if len(parts) >= 3:
                            try:
                                grams = int(parts[2])
                            except:
                                pass
                        
                        user = get_user(uid)
                        if not user:
                            await message.answer("❌ Сначала создайте профиль: /setprofile")
                            return
                        
                        calories_per_100g = get_calories(food_name)
                        
                        if calories_per_100g <= 0:
                            await message.answer(f"❌ Не найден: {food_name}\nПопробуйте: яблоко, банан, курица, пицца, рис, творог")
                            return
                        
                        total_cal = (calories_per_100g * grams) / 100
                        add_log(uid, 'food', f"{food_name} ({grams}г)", total_cal)
                        logger.info(f"Пользователь {uid} записал еду: {food_name} {grams}г = {total_cal:.0f} ккал")
                        
                        stats = get_today_stats(uid)
                        
                        await message.answer(
                            f"✅ {food_name}\n"
                            f"🍎 {calories_per_100g} ккал/100г\n"
                            f"🍽 Порция: {grams}г = {total_cal:.0f} ккал\n"
                            f"📊 Всего съедено: {stats['total_calories']:.0f} ккал"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обработки /food для пользователя {uid}: {e}")
                        await message.answer(f"❌ Ошибка при обработке команды")
                else:
                    await message.answer("❌ Используйте: /food яблоко 200\nПример: /food банан 150")
                    
            elif command == '/workout':
                if len(parts) >= 3:
                    try:
                        workout_type = parts[1]
                        minutes = int(parts[2])
                        user = get_user(uid)
                        
                        if not user:
                            await message.answer("❌ Сначала создайте профиль: /setprofile")
                            return
                        
                        if minutes <= 0:
                            await message.answer("❌ Введите положительное число")
                            return
                        
                        calories = calculate_burned_calories(workout_type, minutes, user['weight'])
                        add_log(uid, 'workout', workout_type, calories)
                        logger.info(f"Пользователь {uid} записал тренировку: {workout_type} {minutes}мин = {calories:.0f} ккал")
                        
                        stats = get_today_stats(uid)
                        
                        await message.answer(
                            f"✅ {workout_type}\n"
                            f"⏱ {minutes} минут\n"
                            f"🔥 Сожжено: {calories:.0f} ккал\n"
                            f"📊 Всего сожжено: {stats['total_burned']:.0f} ккал"
                        )
                    except ValueError:
                        await message.answer("❌ Введите число минут\nПример: /workout бег 30")
                    except Exception as e:
                        logger.error(f"Ошибка обработки /workout для пользователя {uid}: {e}")
                        await message.answer(f"❌ Ошибка при обработке команды")
                else:
                    await message.answer("❌ Используйте: /workout бег 30\nПример: /workout ходьба 45")
                    
            elif command == '/progress':
                try:
                    user = get_user(uid)
                    
                    if not user:
                        await message.answer("❌ Сначала создайте профиль: /setprofile")
                        return
                    
                    logger.info(f"Пользователь {uid} запросил прогресс")
                    stats = get_today_stats(uid)
                    
                    water_drank = stats['total_water']
                    water_goal = user['water_goal']
                    calories_eaten = stats['total_calories']
                    calories_burned = stats['total_burned']
                    calorie_goal = user['calorie_goal']
                    
                    water_progress = min(100, int(water_drank / water_goal * 100)) if water_goal > 0 else 0
                    net_calories = calories_eaten - calories_burned
                    calorie_progress = min(100, max(0, int(net_calories / calorie_goal * 100))) if calorie_goal > 0 else 0
                    
                    water_bar = '█' * int(water_progress / 10) + '░' * (10 - int(water_progress / 10))
                    calorie_bar = '█' * int(calorie_progress / 10) + '░' * (10 - int(calorie_progress / 10))
                    
                    await message.answer(
                        f"📊 Прогресс за {datetime.now().strftime('%d.%m.%Y')}:\n\n"
                        f"💧 ВОДА:\n"
                        f"{water_drank}/{water_goal} мл\n"
                        f"{water_bar} {water_progress}%\n\n"
                        f"🔥 КАЛОРИИ:\n"
                        f"Съедено: {calories_eaten:.0f} ккал\n"
                        f"Сожжено: {calories_burned:.0f} ккал\n"
                        f"Баланс: {net_calories:.0f}/{calorie_goal} ккал\n"
                        f"{calorie_bar} {calorie_progress}%\n\n"
                        f"📈 Активность:\n"
                        f"• Приемов пищи: {stats.get('food_count', 0)}\n"
                        f"• Тренировок: {stats.get('workout_count', 0)}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка получения прогресса для пользователя {uid}: {e}")
                    await message.answer(f"❌ Ошибка при получении прогресса")
                    
            elif command == '/tips':
                try:
                    user = get_user(uid)
                    
                    if not user:
                        await message.answer("❌ Сначала создайте профиль: /setprofile")
                        return
                    
                    logger.info(f"Пользователь {uid} запросил рекомендации")
                    stats = get_today_stats(uid)
                    
                    water_drank = stats['total_water']
                    water_goal = user['water_goal']
                    calories_eaten = stats['total_calories']
                    calories_burned = stats['total_burned']
                    calorie_goal = user['calorie_goal']
                    
                    net_calories = calories_eaten - calories_burned
                    water_left = water_goal - water_drank
                    calorie_left = calorie_goal - net_calories
                    
                    tips = []
                    
                    if water_drank == 0:
                        tips.append("💧 Вы еще не пили воду сегодня. Начните со стакана воды (200-300 мл)")
                    elif water_left > 1500:
                        tips.append(f"💧 Выпейте еще {water_left} мл воды.")
                    elif water_left > 500:
                        tips.append(f"💧 Осталось {water_left} мл воды до нормы")
                    else:
                        tips.append("💧 Отлично! Вы достигли нормы по воде")
                    
                    if net_calories < -500:
                        tips.append(f"🔥 Дефицит калорий: {-net_calories:.0f} ккал. Можно добавить полезные перекусы")
                    elif calorie_left > 1000:
                        tips.append(f"🔥 Можно съесть еще {calorie_left:.0f} ккал до нормы")
                    elif net_calories > calorie_goal:
                        tips.append(f"🏃 Перебор на {net_calories - calorie_goal:.0f} ккал. Добавьте активность")
                    else:
                        tips.append("🔥 Калории в норме. Продолжайте в том же духе!")
                    
                    if stats.get('workout_count', 0) == 0:
                        tips.append("🚶‍♂️ Сегодня не было тренировок. Попробуйте 15-минутную прогулку")
                    elif stats.get('workout_count', 0) == 1:
                        tips.append(f"🏃 Отлично! Сегодня была тренировка: сожжено {calories_burned:.0f} ккал")
                    else:
                        tips.append(f"🏃‍♀️ Отличная активность! {stats.get('workout_count', 0)} тренировок сегодня")
                    
                    tips.append("🍎 Не забывайте про овощи и фрукты")
                    tips.append("⏰ Питайтесь регулярно, каждые 3-4 часа")
                    
                    await message.answer(
                        f"💡 Персональные рекомендации на {datetime.now().strftime('%d.%m.%Y')}:\n\n" +
                        "\n".join(f"• {tip}" for tip in tips)
                    )
                except Exception as e:
                    logger.error(f"Ошибка получения рекомендаций для пользователя {uid}: {e}")
                    await message.answer(f"❌ Ошибка при получении рекомендаций")
                    
            elif command in ['/start', '/help', '/profile', '/setprofile', '/reset']:

                pass
            else:
                await message.answer(
                    "❌ Неизвестная команда\n\n"
                    "📋 Правильные команды:\n"
                    "/water 500 - записать воду\n"
                    "/food яблоко 200 - записать еду\n"
                    "/workout бег 30 - записать тренировку\n"
                    "/start - все команды"
                )
        except Exception as e:
            logger.error(f"Общая ошибка обработки команды от пользователя {uid}: {e}")
            await message.answer("❌ Произошла ошибка при обработке команды")
    else:
        await message.answer("Используйте /start для списка команд")

async def main():
    """Основная функция запуска бота"""
    try:
        logger.info("=" * 50)
        logger.info("🤖 ЗАПУСК БОТА ДЛЯ КОНТРОЛЯ ЗДОРОВЬЯ")
        logger.info("=" * 50)
        
        init_db()
        logger.info("📊 База данных инициализирована")
        
        logger.info("🚀 Бот запущен и ожидает сообщений...")
        logger.info(f"Имя бота: @{(await bot.me()).username}")
        logger.info("=" * 50)
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {e}")
        raise
    finally:
        logger.info("🛑 Бот остановлен")
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:

        logger.critical(f"❌ НЕОБРАБОТАННАЯ ОШИБКА: {e}")
