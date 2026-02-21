import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings:
    def __init__(self):
        self.grid = self._load_grid()
        self.carousel = self._load_carousel()
        self.list_view = self._load_list()

    def _load_grid(self):
        path = os.path.join(SCRIPT_DIR, "settings_grid.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"columns": 4, "tile_width": 200, "tile_height": 300, "spacing": 10}

    def _load_carousel(self):
        path = os.path.join(SCRIPT_DIR, "settings_carousel.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "tile_width": 200,
                "tile_height": 300,
                "visible_count": 5,
                "left_margin": 150,
                "spacing_big": 60,
                "spacing_small": 20
            }

    def _load_list(self):
        path = os.path.join(SCRIPT_DIR, "settings_list.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"spacing": 5}

    def save_grid(self, settings):
        path = os.path.join(SCRIPT_DIR, "settings_grid.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        self.grid = settings

    def save_carousel(self, settings):
        path = os.path.join(SCRIPT_DIR, "settings_carousel.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        self.carousel = settings

    def save_list(self, settings):
        path = os.path.join(SCRIPT_DIR, "settings_list.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        self.list_view = settings