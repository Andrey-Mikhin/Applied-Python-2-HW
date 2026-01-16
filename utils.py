import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')


try:
    from config import FOOD_DB
except ImportError:
    FOOD_DB = {
        'яблоко': 52, 'банан': 96, 'апельсин': 47,
        'курица': 165, 'говядина': 250,
        'хлеб': 265, 'рис': 360, 'шоколад': 550
    }

def get_weather(city):
    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY.startswith(''):
        return 20.0
    
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data['main']['temp']
        else:
            return 20.0
    except:
        return 20.0

def get_calories(food_name):
    food_lower = food_name.lower()
    
    for key, calories in FOOD_DB.items():
        if key in food_lower or food_lower in key:
            return calories
    
    try:
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={food_name}&json=1"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            
            if products:
                first_product = products[0]
                calories = first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
                if calories > 0:
                    return calories
                else:
                    return get_average_calories(food_name)
    except:
        pass
    
    return get_average_calories(food_name)

def get_average_calories(food_name):
    food_lower = food_name.lower()
    
    categories = {
        'овощи': 30, 'фрукты': 50, 'мясо': 250, 'рыба': 200,
        'курица': 165, 'индейка': 135, 'свинина': 242, 'говядина': 250,
        'хлеб': 265, 'макароны': 370, 'рис': 360, 'картофель': 77,
        'яйцо': 155, 'молоко': 60, 'сыр': 350, 'творог': 120,
        'йогурт': 60, 'кефир': 40, 'сметана': 200, 'масло': 750,
        'орехи': 600, 'шоколад': 550, 'печенье': 450, 'торт': 400
    }
    
    for category, calories in categories.items():
        if category in food_lower:
            return calories
    
    if 'салат' in food_lower:
        return 100
    elif 'суп' in food_lower:
        return 80
    elif 'бутерброд' in food_lower:
        return 300
    elif 'пицца' in food_lower:
        return 250
    elif 'бургер' in food_lower:
        return 350
    
    return 150

def calculate_goals(weight, height, age, activity, temp):
    
    base_water = weight * 30
    
    activity_water = (activity // 30) * 200 if activity > 0 else 0
    
    weather_water = 0
    if temp > 30:
        weather_water = 1000
    elif temp > 25:
        weather_water = 500
    elif temp < 0:
        base_water *= 0.9
    
    total_water = base_water + activity_water + weather_water
    water_goal = round(total_water / 100) * 100

    if age <= 0 or weight <= 0 or height <= 0:
        calorie_goal = 2000
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
        
        if activity < 30:
            activity_factor = 1.2
        elif activity < 60:
            activity_factor = 1.375
        elif activity < 90:
            activity_factor = 1.55
        else:
            activity_factor = 1.725
        
        total_calories = bmr * activity_factor
        calorie_goal = round(total_calories / 50) * 50
    
    return water_goal, calorie_goal

def create_progress_bar(percentage, length=10):
    if percentage < 0:
        percentage = 0
    if percentage > 100:
        percentage = 100
    
    filled = int(length * percentage / 100)
    return '█' * filled + '░' * (length - filled)

def calculate_burned_calories(workout_type, minutes, weight):
    met_values = {
        'ходьба': 3.5, 'бег': 8.0, 'велосипед': 6.0, 'плавание': 7.0,
        'йога': 2.5, 'силовая': 5.0, 'тренировка': 5.0, 'отжимания': 3.8,
        'приседания': 5.0, 'планка': 3.0, 'скакалка': 8.5, 'теннис': 7.0,
        'футбол': 7.5, 'баскетбол': 6.5, 'танцы': 5.0, 'аэробика': 6.0
    }
    
    met = met_values.get(workout_type.lower(), 5.0)
    
    hours = minutes / 60
    calories = met * weight * hours
    
    return round(calories)

def get_nutrition_tips(calories_eaten, calories_burned, water_drank, water_goal, workout_count):
    tips = []
    
    water_percentage = (water_drank / water_goal * 100) if water_goal > 0 else 0
    if water_percentage < 50:
        tips.append("💧 Выпейте больше воды.")
    elif water_percentage < 80:
        tips.append("💧 Вы на верном пути! Выпейте еще стакан воды.")
    else:
        tips.append("💧 Отлично! Вы достигли нормы по воде.")
    
    if workout_count == 0:
        tips.append("🏃‍♂️ Попробуйте 15-минутную прогулку или зарядку утром.")
    elif workout_count == 1:
        tips.append("🏃‍♂️ Хорошо! Добавьте силовые упражнения для баланса.")
    else:
        tips.append("🏃‍♂️ Отличная активность! Не забывайте про отдых и восстановление.")
    
    net_calories = calories_eaten - calories_burned
    if net_calories > 500:
        tips.append("🥗 Для снижения калорий попробуйте:\n- Салат с курицей (250 ккал)\n- Овощной суп (150 ккал)\n- Творог с зеленью (180 ккал)")
    elif net_calories < -300:
        tips.append("🥑 Добавьте полезные калории:\n- Авокадо (160 ккал/100г)\n- Орехи (600 ккал/100г)\n- Банан (90 ккал)")
    
    tips.append("🍎 Помните: 5 порций овощей и фруктов в день!")
    tips.append("⏰ Старайтесь есть каждые 3-4 часа для поддержания метаболизма.")
    
    return tips