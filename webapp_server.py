import os
from aiohttp import web

async def health(_req):
    return web.Response(text="Render standby rejimida. Bot foydalanuvchining kompyuterida faol ishlamoqda.")

app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)
