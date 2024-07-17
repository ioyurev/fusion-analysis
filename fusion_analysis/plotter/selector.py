from matplotlib import pyplot as plt
from matplotlib.lines import Line2D


class SelectorArtist(Line2D):
    def __init__(self, x: float, limit_x1: float, limit_x2: float, ax: plt.Axes):
        super().__init__(
            [x, x],
            [0, 1],
            color="black",
            linewidth=1,
            transform=ax.get_xaxis_transform(which="grid"),
        )
        self.limit_x1 = limit_x1
        self.limit_x2 = limit_x2
        ax.add_artist(self)
