#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def healthcheck(request):
    logger.info("Healthcheck request received")
    return web.Response(text="OK")

async def main():
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    app = web.Application()
    app.router.add_get("/", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Server started, listening on port {port}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)
