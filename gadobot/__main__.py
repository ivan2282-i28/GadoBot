import asyncio
import logging
from .bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger("gadobot").info("Bot stopped")