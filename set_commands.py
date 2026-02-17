#!/usr/bin/env python3
import asyncio
from telegram import Bot, BotCommand

async def set_commands():
    bot = Bot(token="YOUR_TOKEN_HERE")  # замените на реальный токен
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("afterdl", "Отчёт после дедлайна"),
        BotCommand("aftertour", "Итоги тура"),
        BotCommand("dssdtempo", "Таблица + темп + LRI"),
        BotCommand("dssdadvice", "Персональные советы"),
        BotCommand("fun", "Игры (DQ, GTD, прогнозы)"),
        BotCommand("halloffame", "Зал славы FPL и Мутантов"),
        BotCommand("other", "Настройки и информация"),
        BotCommand("link", "Привязать FPL ID"),
        BotCommand("cancel", "Отменить текущую операцию"),
    ]
    await bot.set_my_commands(commands)
    print("✅ Команды установлены. Они появятся в меню (кнопка слева снизу).")

if __name__ == "__main__":
    asyncio.run(set_commands())
