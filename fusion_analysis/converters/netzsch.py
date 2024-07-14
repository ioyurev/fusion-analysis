from pathlib import Path

import numpy as np


class NetzschData:
    temp: np.ndarray
    time: np.ndarray
    dta: np.ndarray
    mass: np.ndarray
    segment: np.ndarray


class NetzschSegmentData:
    index: int
    temp: np.ndarray
    time: np.ndarray
    dta: np.ndarray
    mass: np.ndarray


def _find_data(file_content: list[str]):
    for i, line in enumerate(file_content):
        if line.startswith("##"):
            return i + 1
    raise Exception("No data found")


def n2f(path: Path):
    with open(path) as f:
        file_content = f.read().split("\n")
    i = _find_data(file_content)
    arr = np.loadtxt(file_content[i:], delimiter=";").transpose()
    table_header = file_content[i - 1][2:].split(";")

    data = NetzschData()
    for i, item in enumerate(table_header):
        if item.startswith("Temp"):
            data.temp = arr[i]
        elif item.startswith("Time"):
            data.time = arr[i]
        elif item.startswith("DTA"):
            data.dta = arr[i]
        elif item.startswith("Mass"):
            data.mass = arr[i]
        elif item.startswith("Segment"):
            data.segment = arr[i]

    segments: list[NetzschSegmentData] = list()
    for segment in np.unique(data.segment):
        i = np.where(data.segment == segment)[0]
        segment_data = NetzschSegmentData()
        segment_data.index = int(segment) - 1
        segment_data.temp = data.temp[i]
        segment_data.time = data.time[i]
        segment_data.dta = data.dta[i]
        segment_data.mass = data.mass[i]
        segments.append(segment_data)

    return segments


if __name__ == "__main__":
    from matplotlib import pyplot as plt

    segments = n2f(Path("examples/2023.07.05 66.7 Gd2Se3 33.3 Gd2O3.txt"))
    plt.figure()
    for s in segments:
        plt.plot(s.time, s.dta)

    plt.tight_layout()
    plt.show()
