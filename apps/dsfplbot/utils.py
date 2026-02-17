from datetime import datetime
import pytz

def time_until_deadline(deadline_str: str) -> str:
    """
    Возвращает строку с оставшимся временем до дедлайна.
    Предполагается, что deadline_str задан в московском времени (UTC+3).
    Если временная зона не указана, добавляем +03:00.
    """
    # Если в строке нет временной зоны, добавляем московское время (UTC+3)
    if '+' not in deadline_str and 'Z' not in deadline_str and 'z' not in deadline_str:
        deadline_str += '+03:00'
    
    deadline = datetime.fromisoformat(deadline_str)
    now = datetime.now(pytz.UTC)
    
    if now >= deadline:
        return "⏳ Дедлайн прошёл!"
    
    diff = deadline - now
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    return f"⏳ До дедлайна: {days}д {hours}ч {minutes}м"
