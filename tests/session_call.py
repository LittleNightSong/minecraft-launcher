import asyncio

from app.core.network import Session

session = Session()


async def main():
    # async with session:
    #     print(await session.call("https://api.github.com"))
    #     resp = await session.get("https://api.github.com", stream=True)
    #     print(type(resp))
    #     print(resp.status_code)

    session_2 = Session(disable_http1=True, happy_eyeballs=True)
    async with session_2:
        resp = await session_2.request(
            "GET",
            "https://api.github.com",
            # stream=True
        )
        print(type(resp))
        # await resp
        print(resp.__lazy_attrs__)
        print(resp)
        print(resp.status_code)
        print(await resp.iter_content())
        print(await resp.content)
if __name__ == '__main__':
    asyncio.run(main())
