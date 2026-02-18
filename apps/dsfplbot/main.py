#!/usr/bin/env python3
"""
DSFPLBot — точка входа.
Запускает healthcheck-сервер и Telegram-бота.
"""
import os
import sys
import asyncio
import signal
import logging
import datetime

from aiohttp import web
from apps.dsfplbot.database import init_db, import_legacy_csv, ensure_user_fpl_table

# ── Логирование ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.info("=== DSFPLBot STARTING ===")


# ── Healthcheck-сервер ──

async def healthcheck(request):
    return web.Response(text="OK")


async def run_healthcheck():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Healthcheck server started on port {port}")
    await asyncio.Event().wait()


# ── Бот ──

async def run_healthcheck_and_bot():
    # 1. Сначала запускаем healthcheck (Railway ожидает ответ на порту)
    healthcheck_task = asyncio.create_task(run_healthcheck())
    await asyncio.sleep(1)

    # 2. Импортируем модули
    logger.info("Importing modules...")
    try:
        from apps.dsfplbot.config import TOKEN, FPL_LEAGUE_ID, ADMIN_USER_ID
        from apps.dsfplbot.database import init_db, import_legacy_csv
        from apps.dsfplbot.handlers import (
            start, link_start, link_get_id, link_cancel,
            afterdl, aftertour,
            dssdtempo_start, dssdtempo_get_weeks, dssdtempo_cancel,
            dssdadvice, export_data,
            WEEKS, LINK_FPL,
        )
        from apps.dsfplbot.fun import (
            fun, fun_callback, dq, answer, gtd, predictions,
            scoreboard, daily_quiz_job
        )
        from apps.dsfplbot.halloffame import halloffame, hof_callback
        from apps.dsfplbot.other import other, other_callback

        logger.info("All modules imported successfully")
    except Exception as e:
        logger.exception("Module import failed, healthcheck keeps running")
        await asyncio.Event().wait()
        return

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        await asyncio.Event().wait()
        return

    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        ConversationHandler, MessageHandler, filters
    )
    from telegram.request import HTTPXRequest

    application = None

    # ── post_init: создание таблиц, импорт CSV ──
    async def post_init(app):
        logger.info("Running post_init...")
        await init_db()
        await ensure_user_fpl_table()
        try:
            csv_path = os.path.join(os.path.dirname(__file__), "FPL League History.csv")
            await import_legacy_csv(csv_path)
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
        logger.info("post_init complete")

    # ── Graceful shutdown ──
    async def shutdown_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        if application:
            await application.stop()
            await application.shutdown()

    # ── Создание приложения ──
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    application = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .post_init(post_init)
        .build()
    )

    # ── Сигналы ──
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown_handler(s, None))
        )

    # ── Обработчики команд ──
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("afterdl", afterdl))
    application.add_handler(CommandHandler("aftertour", aftertour))
    application.add_handler(CommandHandler("dssdadvice", dssdadvice))
    application.add_handler(CommandHandler("fun", fun))
    application.add_handler(CommandHandler("halloffame", halloffame))
    application.add_handler(CommandHandler("other", other))
    application.add_handler(CommandHandler("export_data", export_data))
    application.add_handler(CommandHandler("dq", dq))
    application.add_handler(CommandHandler("answer", answer))
    application.add_handler(CommandHandler("gtd", gtd))
    application.add_handler(CommandHandler("predictions", predictions))
    application.add_handler(CommandHandler("scoreboard", scoreboard))

    # ── ConversationHandlers ──
    dssdtempo_conv = ConversationHandler(
        entry_points=[CommandHandler("dssdtempo", dssdtempo_start)],
        states={
            WEEKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, dssdtempo_get_weeks)]
        },
        fallbacks=[CommandHandler("cancel", dssdtempo_cancel)]
    )
    application.add_handler(dssdtempo_conv)

    link_conv = ConversationHandler(
        entry_points=[CommandHandler("link", link_start)],
        states={
            LINK_FPL: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_get_id)]
        },
        fallbacks=[CommandHandler("cancel", link_cancel)]
    )
    application.add_handler(link_conv)

    # ── Callback-кнопки ──
    application.add_handler(CallbackQueryHandler(fun_callback, pattern="^fun_|^score_|^back_to_fun|^gtd_"))
    application.add_handler(CallbackQueryHandler(hof_callback, pattern="^hof_|^back_to_hof"))
    application.add_handler(CallbackQueryHandler(other_callback, pattern="^other_|^other$|^notif_toggle|^remind_toggle|^back_to_main"))

    # ── Ежедневный квиз (12:00 UTC) ──
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_daily(
            daily_quiz_job,
            time=datetime.time(hour=12, minute=0),
            days=tuple(range(7))
        )

    # ── Запуск ──
    await application.initialize()
    await application.start()
    logger.info("Bot started")

    await application.updater.start_polling()
    logger.info("Polling started, bot is running")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(run_healthcheck_and_bot())
    except Exception as e:
        logger.exception("Fatal error in main")
        sys.exit(1)
