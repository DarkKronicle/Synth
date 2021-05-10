import traceback

import toml
import pathlib


class Config:
    """
    Basically reads a toml file and then provides a nice interface with it.
    """

    def __init__(self, file: pathlib.Path):
        self.file = file
        self.data = {}
        self.loadfile()

    def loadfile(self):
        try:
            data = self.file.read_text()
        except Exception:
            traceback.print_exc()
            return
        self.data = toml.loads(data)

    def __getitem__(self, item):
        return self.data[item]

    def __contains__(self, item):
        return item in self.data