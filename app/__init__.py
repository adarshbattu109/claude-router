import uvicorn

from helpers import config


def main(host: str = config.HOST, port: int = config.PORT):
    uvicorn.run("app.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
