from pickledb import AsyncPickleDB
from MicroPie import App
import orjson
import uvicorn

DB_NAME = input('Enter database name: ')
db = AsyncPickleDB(DB_NAME)


class Root(App):

    async def set(self, key, value):
        await db.aset(key, value)
        return orjson.dumps({key: value})

    async def get(self, key):
        value = await db.aget(key)
        return orjson.dumps({key: value})

    async def remove(self, key):
        await db.aremove(key)
        return orjson.dumps({'action': 'removed'})

    async def purge(self):
        await db.apurge()
        return orjson.dumps({'action': 'purge'})

    async def all(self):
        return orjson.dumps(await db.aall())

    async def save(self):
        await db.asave()
        return orjson.dumps({'action': 'save'})


app = Root()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5272)
