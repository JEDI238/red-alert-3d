from ursina import Ursina

from game import RTSGame


def main():
    app = Ursina()
    RTSGame()
    app.run()


if __name__ == "__main__":
    main()
