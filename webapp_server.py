"""
Render yoki boshqa hostinglar uchun moslik fayli (Start Command agar python webapp_server.py bo'lib qolgan bo'lsa ham bot.py ni ishga tushiradi).
"""
import asyncio
from bot import main

if __name__ == "__main__":
    asyncio.run(main())
