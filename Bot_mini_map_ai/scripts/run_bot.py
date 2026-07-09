import asyncio
import Bot_mini_map_ai.main_bot.main as main_bot
import Bot_mini_map_ai.support_bot.main_support as support_bot


async def run():
    await asyncio.gather(
        main_bot.main(),
        support_bot.main(),
)

if __name__ == "__main__":
    asyncio.run(run())