import numpy as np
from sympy.core import Symbol
from sympy.solvers.solvers import nsolve
from sympy.utilities import lambdify
import matplotlib.pyplot as plt
import math

LINEAR_TYPE = 0
BEZIER_TYPE = 1

def xand_gate(a, b):
    """
    Возвращает True, если оба аргумента равны False или True, иначе возвращает False.

    Args:
        a (bool): Первый аргумент.
        b (bool): Второй аргумент.

    Returns:
        bool: Результат операции XAND.
    """
    return (not a and not b) or (a and b)

def baseline_temp(data_temp, data_dta):
    x = Symbol('x')
    coeff = np.polyfit(data_temp, data_dta, 4)
    temp_expr = coeff[0] * x**4 + coeff[1] * x**3 + coeff[2] * x**2 + coeff[3] * x + coeff[4]
    return temp_expr

def calc_peakonset(t1, t2, data_t: np.ndarray, data_dta: np.ndarray, data_ddta: np.ndarray, expr_baseline, is_onset:bool, peak_exo: bool):   
    x = Symbol('x')
    i1 = find_nearest(data_t, t1)
    i2 = find_nearest(data_t, t2)
    if i1 > i2:
        i1, i2 = swap_values(i1, i2)
    
    # fig, ax = plt.subplots()
    # ax.plot(data_t[i1:i2], data_dta[i1:i2])
    # ax.plot(data_t[i1:i2], data_ddta[i1:i2])
    # fig.show()

    if xand_gate(is_onset, peak_exo):
        bt = max(data_ddta[i1:i2])
    else:
        bt = min(data_ddta[i1:i2])
    ci = np.where(data_ddta[i1:i2] == bt)[0][0] + i1
    xt = data_t[ci]
    yt = data_dta[ci]
    at = yt - bt * xt
    expr_tangent = at + bt * x
    xi = float(nsolve(expr_tangent - expr_baseline, x, xt))
    bi = find_nearest(data_t, xi)
    return ci, bi

def sround(x: float, n: int):
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))

def swap_values(a, b):
    return b, a

def PolyArea(vertices):
    # print(vertices)
    # x, y = np.split(vertices, 2, axis=1)
    x, y = np.transpose(vertices)
    # source: https://stackoverflow.com/a/30408825/11709825
    return 0.5*np.abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))

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
    x = Symbol('x')
    # t, x = sympy.symbols('t x')
    if baselinetype == LINEAR_TYPE:
        # print("* базовая линия линейная")
        x1 = xdata[i1]
        x2 = xdata[i2]
        y1 = ydata[i1]
        y2 = ydata[i2]
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - x1 * slope
        y_expr = intercept + slope * x
    elif baselinetype == BEZIER_TYPE:
        # print("* базовая линия безье")
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

        a = x1 - 2 * x2 + x3
        b = 2 * (x2 -x1)
        c = x1 - x
        d = (b ** 2) - 4 * a * c

        t_expr = (-b + (d ** (1 / 2))) / (2 * a)
        y_expr = ((1 - t_expr) ** 2) * y1 + 2 * (1 - t_expr) * t_expr * y2 + (t_expr ** 2) * y3
    else:
        print('\n* ERROR: none/wrong baselinetype provided\n')
        return
    # print("* уравнение базовой линии: " + str(y_expr))
    f = lambdify(x, y_expr, 'numpy')
    xdata = np.asarray(xdata)
    baseline_y = f(xdata[i1:i2])
    # print(type(y_expr))
    return baseline_y, y_expr
