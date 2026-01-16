import sqlite3
from datetime import datetime, date

DB_NAME = "health.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        weight REAL, 
        height REAL, 
        age INTEGER,
        activity INTEGER, 
        city TEXT,
        water_goal INTEGER, 
        calorie_goal INTEGER,
        water_drank INTEGER DEFAULT 0,
        calories_eaten REAL DEFAULT 0,
        calories_burned REAL DEFAULT 0,
        last_reset_date DATE)
    ''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,  -- 'water', 'food', 'workout'
        value TEXT,
        amount REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    ''')
    
    cur.execute('CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)')
    
    conn.commit()
    conn.close()
    print(f"База данных {DB_NAME} инициализирована")

def save_user(user_id, **data):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
    
    if cur.fetchone():
        cur.execute('''
        UPDATE users SET 
            weight = ?, height = ?, age = ?, activity = ?, city = ?,
            water_goal = ?, calorie_goal = ?
        WHERE user_id = ?
        ''', (
            data.get('weight'), data.get('height'), data.get('age'),
            data.get('activity'), data.get('city'),
            data.get('water_goal'), data.get('calorie_goal'), 
            user_id
        ))
    else:
        cur.execute('''
        INSERT INTO users 
        (user_id, weight, height, age, activity, city, 
         water_goal, calorie_goal, last_reset_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, data.get('weight'), data.get('height'), data.get('age'),
            data.get('activity'), data.get('city'),
            data.get('water_goal'), data.get('calorie_goal'),
            date.today().isoformat()
        ))
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        try:
            return {
                'user_id': row[0],
                'weight': row[1] if len(row) > 1 else 0,
                'height': row[2] if len(row) > 2 else 0,
                'age': row[3] if len(row) > 3 else 0,
                'activity': row[4] if len(row) > 4 else 0,
                'city': row[5] if len(row) > 5 else '',
                'water_goal': row[6] if len(row) > 6 else 0,
                'calorie_goal': row[7] if len(row) > 7 else 0,
                'water_drank': row[8] if len(row) > 8 else 0,
                'calories_eaten': row[9] if len(row) > 9 else 0,
                'calories_burned': row[10] if len(row) > 10 else 0,
                'last_reset_date': row[11] if len(row) > 11 else None
            }
        except IndexError:
            return None
    return None

def add_log(user_id, log_type, value, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    _check_and_reset_daily_data(user_id, cur)
    
    cur.execute('''
    INSERT INTO logs (user_id, type, value, amount)
    VALUES (?, ?, ?, ?)
    ''', (user_id, log_type, str(value), float(amount)))
    
    if log_type == 'water':
        cur.execute('''
        UPDATE users SET water_drank = water_drank + ? 
        WHERE user_id = ?
        ''', (float(amount), user_id))
    elif log_type == 'food':
        cur.execute('''
        UPDATE users SET calories_eaten = calories_eaten + ? 
        WHERE user_id = ?
        ''', (float(amount), user_id))
    elif log_type == 'workout':
        cur.execute('''
        UPDATE users SET calories_burned = calories_burned + ? 
        WHERE user_id = ?
        ''', (float(amount), user_id))
    
    conn.commit()
    conn.close()
    return True

def _check_and_reset_daily_data(user_id, cursor):
    cursor.execute('SELECT last_reset_date FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        last_reset = date.fromisoformat(result[0])
        today = date.today()
        
        if last_reset < today:
            cursor.execute('''
            UPDATE users SET 
                water_drank = 0,
                calories_eaten = 0,
                calories_burned = 0,
                last_reset_date = ?
            WHERE user_id = ?
            ''', (today.isoformat(), user_id))

def get_today_stats(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    _check_and_reset_daily_data(user_id, cur)
    conn.commit()
    
    user = get_user(user_id)
    if not user:
        conn.close()
        return {}
    
    cur.execute('''
    SELECT type, COUNT(*) as count, SUM(amount) as total
    FROM logs 
    WHERE user_id = ? AND DATE(created_at) = DATE('now')
    GROUP BY type
    ''', (user_id,))
    
    stats = {
        'food_count': 0,
        'workout_count': 0,
        'food_total': 0,
        'workout_total': 0,
        'water_total': 0}
    
    for log_type, count, total in cur.fetchall():
        if log_type == 'food':
            stats['food_count'] = count
            stats['food_total'] = total or 0
        elif log_type == 'workout':
            stats['workout_count'] = count
            stats['workout_total'] = total or 0
        elif log_type == 'water':
            stats['water_total'] = total or 0
    
    conn.close()
    
    return {
        'total_water': user['water_drank'],
        'total_calories': user['calories_eaten'],
        'total_burned': user['calories_burned'],
        'water_goal': user['water_goal'],
        'calorie_goal': user['calorie_goal'],
        'calorie_balance': user['calories_eaten'] - user['calories_burned'],
        'water_percentage': (user['water_drank'] / user['water_goal'] * 100) if user['water_goal'] > 0 else 0,
        **stats}

def clear_user_logs(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    try:
        cur.execute('DELETE FROM logs WHERE user_id = ?', (user_id,))
        
        cur.execute('''
        UPDATE users SET 
            water_drank = 0,
            calories_eaten = 0,
            calories_burned = 0,
            last_reset_date = ?
        WHERE user_id = ?
        ''', (date.today().isoformat(), user_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при очистке логов: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_user_history(user_id, days=7):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute('''
    SELECT type, value, amount, created_at
    FROM logs 
    WHERE user_id = ? AND DATE(created_at) >= DATE('now', ?)
    ORDER BY created_at DESC
    ''', (user_id, f'-{days} days'))
    
    history = []
    for row in cur.fetchall():
        history.append({
            'type': row[0],
            'value': row[1],
            'amount': row[2],
            'created_at': row[3]
        })
    
    conn.close()
    return history

def delete_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    try:
        cur.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при удалении пользователя: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def reset_daily_data(user_id):
    return clear_user_logs(user_id)

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute('''
    SELECT user_id, city, water_drank, calories_eaten, calories_burned
    FROM users
    ORDER BY user_id
    ''')
    
    users = []
    for row in cur.fetchall():
        users.append({
            'user_id': row[0],
            'city': row[1],
            'water_drank': row[2],
            'calories_eaten': row[3],
            'calories_burned': row[4]
        })
    
    conn.close()
    return users