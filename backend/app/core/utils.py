import asyncio


async def startup_event():
    await asyncio.sleep(1)
    print("Startup Successful")


async def shutdown_event():
    await asyncio.sleep(1)
    print("Shutdown Successful")
