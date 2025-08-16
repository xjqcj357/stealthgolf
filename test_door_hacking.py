import os
import pytest

os.environ['KIVY_WINDOW'] = 'mock'
kivy = pytest.importorskip('kivy')
from kivy.core.window import Window
Window.size = (480, 800)
from kivy.app import App

class DummyApp:
    selected_color = (1, 1, 1, 1)

App.get_running_app = staticmethod(lambda: DummyApp())

from stealth_golf import StealthGolf


def test_door_opens_after_hack():
    game = StealthGolf()
    game.width = 480
    game.height = 800
    game.floors = [{
        'walls': [],
        'colliders': [],
        'decor': [],
        'agents': [],
        'stairs': [],
        'doors': [
            {'rect': [50, 40, 40, 20], 'screen': [40, 40, 10, 20], 'color': 'red', 'open': False}
        ]
    }]
    game.current_floor = 0
    game._apply_floor(0)
    game.ball.x = 45
    game.ball.y = 50
    for _ in range(25):
        game.update(0.1)
    assert game.doors[0]['open'] is True
