import numpy as np
import itertools
import sympy
import matplotlib.pyplot as plt
import math

LINEAR_TYPE = 0
BEZIER_TYPE = 1

colors = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])

def sround(x, n: int):
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))

def swap_values(a, b):
    return b, a

def PolyArea(vertices):
    # print(vertices)
    # x, y = np.split(vertices, 2, axis=1)
    x, y = np.transpose(vertices)
    # source: https://stackoverflow.com/a/30408825/11709825
    return 0.5*np.abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))

def get_next_color():
    return next(colors)

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx

def derivative(xdata, ydata):
    # print('* считаем производную')
    return np.insert(
        np.diff(ydata) / np.diff(xdata), 0, 0, axis=0
    )

def make_peakbaseline(baselinetype, i1, i2, xdata, ydata):
    baseline_y = []
    x = sympy.Symbol('x')
    # t, x = sympy.symbols('t x')
    if baselinetype == LINEAR_TYPE:
        print("* making linear baseline")
        x1 = xdata[i1]
        x2 = xdata[i2]
        y1 = ydata[i1]
        y2 = ydata[i2]
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - x1 * slope
        y_expr = intercept + slope * x
    elif baselinetype == BEZIER_TYPE:
        print("* making bezier baseline")
        x1prev = xdata[i1 - 1]
        x1 = xdata[i1]
        y1prev = ydata[i1 - 1]
        y1 = ydata[i1]
        b1 = (y1 - y1prev) / (x1 - x1prev)
        a1 = y1 - x1 * b1

        x3prev = xdata[i2 + 1]
        x3 = xdata[i2]
        y3prev = ydata[i2 + 1]
        y3 = ydata[i2]
        b3 = (y3 - y3prev) / (x3 - x3prev)
        a3 = y3 - x3 * b3

        x2 = (a3 - a1) / (b1 - b3)
        y2 = a1 + b1 * x2

        # fx = ((1 - t) ** 2) * x1 + 2 * (1 - t) * t * x2 + (t ** 2) * x3
        # y = ((1 - t) ** 2) * y1 + 2 * (1 - t) * t * y2 + (t ** 2) * y3

        # poly = sympy.Poly(fx, t)
        # coeffs = poly.coeffs()
        # a = coeffs[0]
        # b = coeffs[1]
        # c = coeffs[2] - x
        a = x1 - 2 * x2 + x3
        b = 2 * (x2 -x1)
        c = x1 - x
        D = (b ** 2) - 4 * a * c

        t_expr = (-b + (D ** (1 / 2))) / (2 * a)
        y_expr = ((1 - t_expr) ** 2) * y1 + 2 * (1 - t_expr) * t_expr * y2 + (t_expr ** 2) * y3
    else:
        print('\n* ERROR: none/wrong baselinetype provided\n')
        return
    print("* baseline expression: " + str(y_expr))
    f = sympy.lambdify(x, y_expr, 'numpy')
    xdata = np.asarray(xdata)
    baseline_y = f(xdata[i1:i2])
    return np.array(baseline_y, dtype=float), y_expr
