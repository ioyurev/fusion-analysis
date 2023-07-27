import numpy as np
from typing import Callable
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
    coeff = np.polyfit(data_temp, data_dta, 4)
    temp_expr = lambda x: coeff[0] * x**4 + coeff[1] * x**3 + coeff[2] * x**2 + coeff[3] * x + coeff[4]
    return temp_expr

def calc_peakonset(t1, t2, data_t: np.ndarray, data_dta: np.ndarray, data_ddta: np.ndarray, expr_baseline: Callable, is_onset:bool, peak_exo: bool):   
    i1 = find_nearest(data_t, t1)
    i2 = find_nearest(data_t, t2)
    if i1 > i2:
        i1, i2 = swap_values(i1, i2)
    if xand_gate(is_onset, peak_exo):
        bt = max(data_ddta[i1:i2])
    else:
        bt = min(data_ddta[i1:i2])
    ci = np.where(data_ddta[i1:i2] == bt)[0][0] + i1
    xt = data_t[ci]
    yt = data_dta[ci]
    at = yt - bt * xt
    expr_tangent = lambda x: at + bt * x
    f = lambda x: expr_tangent(x) - expr_baseline(x)
    xi = newton(
        f=f,
        Df = lambda x: derivative_func(f=f, a=x, h=1e-7),
        x0=xt,
        epsilon=1e-7,
        max_iter=10
    )
    bi = find_nearest(data_t, xi)
    return ci, bi

def sround(x: float, n: int):
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))

def swap_values(a, b):
    return b, a

def PolyArea(vertices):
    x, y = np.transpose(vertices)
    # source: https://stackoverflow.com/a/30408825/11709825
    return 0.5*np.abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx

def derivative_data(xdata, ydata):
    return np.insert(
        np.diff(ydata) / np.diff(xdata), 0, 0, axis=0
    )

def make_peakbaseline(baselinetype, i1, i2, xdata, ydata):
    baseline_y = []
    if baselinetype == LINEAR_TYPE:
        x1 = xdata[i1]
        x2 = xdata[i2]
        y1 = ydata[i1]
        y2 = ydata[i2]
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - x1 * slope
        y_expr = lambda x: intercept + slope * x
    elif baselinetype == BEZIER_TYPE:
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
        c = lambda x: x1 - x
        d = lambda x: (b ** 2) - 4 * a * c(x)

        t_expr = lambda x: (-b + (d(x) ** (1 / 2))) / (2 * a)
        y_expr = lambda x: ((1 - t_expr(x)) ** 2) * y1 + 2 * (1 - t_expr(x)) * t_expr(x) * y2 + (t_expr(x) ** 2) * y3
    else:
        print('\n* ERROR: none/wrong baselinetype provided\n')
        return
    baseline_y = y_expr(np.asarray(xdata)[i1:i2])
    return baseline_y, y_expr

def newton(f,Df,x0,epsilon,max_iter):
    # source: https://patrickwalls.github.io/mathematicalpython/root-finding/newton/
    '''Approximate solution of f(x)=0 by Newton's method.

    Parameters
    ----------
    f : function
        Function for which we are searching for a solution f(x)=0.
    Df : function
        Derivative of f(x).
    x0 : number
        Initial guess for a solution f(x)=0.
    epsilon : number
        Stopping criteria is abs(f(x)) < epsilon.
    max_iter : integer
        Maximum number of iterations of Newton's method.

    Returns
    -------
    xn : number
        Implement Newton's method: compute the linear approximation
        of f(x) at xn and find x intercept by the formula
            x = xn - f(xn)/Df(xn)
        Continue until abs(f(xn)) < epsilon and return xn.
        If Df(xn) == 0, return None. If the number of iterations
        exceeds max_iter, then return None.

    Examples
    --------
    >>> f = lambda x: x**2 - x - 1
    >>> Df = lambda x: 2*x - 1
    >>> newton(f,Df,1,1e-8,10)
    Found solution after 5 iterations.
    1.618033988749989
    '''
    xn = x0
    for n in range(0,max_iter):
        fxn = f(xn)
        if abs(fxn) < epsilon:
            print(f'Found solution after {n} iterations.')
            return xn
        Dfxn = Df(xn)
        if Dfxn == 0:
            print('Zero derivative. No solution found.')
            return None
        xn = xn - fxn/Dfxn
    print('Exceeded maximum iterations. No solution found.')
    return None

def derivative_func(f,a,method='central',h=0.01):
    # source: https://patrickwalls.github.io/mathematicalpython/differentiation/differentiation/
    '''Compute the difference formula for f'(a) with step size h.

    Parameters
    ----------
    f : function
        Vectorized function of one variable
    a : number
        Compute derivative at x = a
    method : string
        Difference formula: 'forward', 'backward' or 'central'
    h : number
        Step size in difference formula

    Returns
    -------
    float
        Difference formula:
            central: f(a+h) - f(a-h))/2h
            forward: f(a+h) - f(a))/h
            backward: f(a) - f(a-h))/h            
    '''
    if method == 'central':
        return (f(a + h) - f(a - h))/(2*h)
    elif method == 'forward':
        return (f(a + h) - f(a))/h
    elif method == 'backward':
        return (f(a) - f(a - h))/h
    else:
        raise ValueError("Method must be 'central', 'forward' or 'backward'.")
