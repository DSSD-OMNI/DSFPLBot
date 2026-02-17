#!/usr/bin/env python3
"""
Скрипт для установки команд бота в меню Telegram (кнопка слева снизу).
Запустите этот скрипт один раз после получения токена.
"""

import asyncio
from telegram import Bot, BotCommand
from apps.dsfplbot.config import TOKEN  # предполагается, что файл config.py лежит рядом

async def set_commands():
    bot = Bot(token=TOKEN)
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("afterdl", "Отчёт после дедлайна тура"),
        BotCommand("aftertour", "Итоги завершённого тура"),
        BotCommand("dssdtempo", "Таблица лиги + темп + LRI"),
        BotCommand("dssdadvice", "Персональные трансферные советы"),
        BotCommand("fun", "Mutantos Game Arena (игры)"),
        BotCommand("halloffame", "Зал славы лиги FPL и Мутантов"),
        BotCommand("other", "Настройки и информация о боте"),
        BotCommand("link", "Привязать свой FPL ID"),
        BotCommand("cancel", "Отменить текущую операцию"),
    ]
    await bot.set_my_commands(commands)
    print("✅ Команды успешно установлены! Они появятся в меню (кнопка слева снизу).")

if __name__ == "__main__":
    asyncio.run(set_commands())
