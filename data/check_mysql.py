"""
Проверка доступных таблиц в MySQL
"""
import mysql.connector
from config import settings

def check_mysql_tables():
    """Проверяем какие таблицы есть в MySQL"""
    try:
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            charset='utf8mb4'
        )
        
        cursor = connection.cursor()
        
        # Получаем список таблиц
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print("📋 Доступные таблицы в базе данных:")
        for table in tables:
            table_name = table[0]
            print(f"  - {table_name}")
            
            # Проверяем есть ли FIAS-подобные таблицы
            if 'fias' in table_name.lower() or 'address' in table_name.lower():
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                print(f"    Столбцы:")
                for col in columns[:5]:  # Показываем первые 5 столбцов
                    print(f"      - {col[0]} ({col[1]})")
                if len(columns) > 5:
                    print(f"      ... и ещё {len(columns) - 5} столбцов")
                
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"    Записей: {count}")
                print()
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ Ошибка подключения к MySQL: {e}")

if __name__ == "__main__":
    check_mysql_tables()
