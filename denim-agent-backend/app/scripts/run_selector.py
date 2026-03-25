import asyncio
import sys

from app.services.selector import run_phase_4a_selector


async def main():
    batch_size = 25
    if len(sys.argv) > 1:
        try:
            batch_size = int(sys.argv[1])
        except ValueError:
            print("Invalid batch size, using 25")

    await run_phase_4a_selector(batch_size=batch_size)


if __name__ == "__main__":
    asyncio.run(main())