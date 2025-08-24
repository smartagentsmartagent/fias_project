"""
Исследование структуры таблицы address_fias_gar
"""
import mysql.connector
from config import settings

def explore_gar_table():
    """Исследуем структуру таблицы address_fias_gar"""
    try:
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            charset='utf8mb4'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # Полная структура таблицы
        cursor.execute("DESCRIBE address_fias_gar")
        columns = cursor.fetchall()
        
        print("📊 Структура таблицы address_fias_gar:")
        for col in columns:
            print(f"  - {col['Field']}: {col['Type']} ({'NULL' if col['Null'] == 'YES' else 'NOT NULL'})")
        print()
        
        # Примеры данных
        cursor.execute("SELECT * FROM address_fias_gar LIMIT 10")
        rows = cursor.fetchall()
        
        print("📋 Примеры данных:")
        for i, row in enumerate(rows[:3]):
            print(f"Запись {i+1}:")
            for key, value in row.items():
                if value is not None:
                    print(f"  {key}: {value}")
            print()
        
        # Статистика по уровням (если есть поле уровня)
        possible_level_fields = ['AOLEVEL', 'level', 'OBJECTLEVELID', 'LEVELID']
        level_field = None
        
        for field in possible_level_fields:
            try:
                cursor.execute(f"SELECT DISTINCT {field} FROM address_fias_gar WHERE {field} IS NOT NULL LIMIT 10")
                levels = cursor.fetchall()
                if levels:
                    level_field = field
                    print(f"📈 Уровни в поле {field}:")
                    for level in levels:
                        print(f"  - {level[field]}")
                    print()
                    break
            except:
                continue
        
        # Статистика по регионам (если есть поле региона)
        possible_region_fields = ['REGIONCODE', 'region_code', 'REGIONID']
        region_field = None
        
        for field in possible_region_fields:
            try:
                cursor.execute(f"SELECT {field}, COUNT(*) as cnt FROM address_fias_gar WHERE {field} IS NOT NULL GROUP BY {field} ORDER BY cnt DESC LIMIT 10")
                regions = cursor.fetchall()
                if regions:
                    region_field = field
                    print(f"🗺️ Топ регионов в поле {field}:")
                    for region in regions:
                        print(f"  - {region[field]}: {region['cnt']} записей")
                    print()
                    break
            except:
                continue
        
        cursor.close()
        connection.close()
        
        return level_field, region_field
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None, None

if __name__ == "__main__":
    explore_gar_table()
