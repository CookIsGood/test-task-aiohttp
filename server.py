import asyncio
import websockets


async def response(websocket, path):
    while True:
        message = await websocket.recv()
        print(message)
        await websocket.send(message)


start_server = websockets.serve(response, '127.0.0.1', 9999, ping_interval=None)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
