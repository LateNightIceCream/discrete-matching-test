import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from scipy.optimize import minimize
import numpy as np
import matplotlib.pyplot as plt

Z_L = 200 - 100j
Z_0 = 50
f_0_str = '500MHz'


# frequency band centered on the frequency of interest
frequency = rf.Frequency(start=300, stop=700, npoints=401, unit='MHz')
# transmission line Media
line = rf.DefinedGammaZ0(frequency=frequency, z0=Z_0)
# load Network
load = line.load(rf.zl_2_Gamma0(Z_0, Z_L))


def matching_network_LC_1(L1, C1, L2, C2):
    ' L and C in nH and pF'
    l1 = L1 * 1e-9
    l2 = L2 * 1e-9
    c1 = C1 * 1e-12
    c2 = C2 * 1e-12
    return line.inductor(l1)**line.shunt_capacitor(c1)**line.shunt_inductor(l2)**line.capacitor(c2)**load


def matching_network_LC_2(L, C):
    ' L and C in nH and pF'
    return line.capacitor(C*1e-12)**line.shunt_inductor(L*1e-9)**load


# initial guess values
L0 = 10 # nH
C0 = 1 # pF
L1 = 10 # nH
C1 = 1 # pF
x0 = (L0, C0, L1, C1)
x1 = (L0, C0)
# bounds
L_minmax = (1, 100) #nH
C_minmax = (0.1, 10) # pF
L1_minmax = (1, 100) #nH
C1_minmax = (0.1, 10) # pF

def objective_function_1(x, f0=f_0_str):
    _ntw = matching_network_LC_1(*x)
    max_db = max(rf.mathFunctions.complex_2_db(_ntw['400mhz-600mhz'].s11.s))
    return max_db[0][0]
    #return np.abs(_ntw[f_0_str].s).ravel()


def objective_function_2(x, f0=f_0_str):
    _ntw = matching_network_LC_2(*x)
    return np.abs(_ntw[f_0_str].s).ravel()


res1 = minimize(objective_function_1, x0, bounds=(L_minmax, C_minmax, L1_minmax, C1_minmax))
print(f'Optimum found for LC network 1: L={res1.x[0]} nH and C={res1.x[1]} pF')

ntw1 = matching_network_LC_1(*res1.x)

ntw1.plot_s_db(lw=2, label='LC network 1')

save_all_figs('./plots', format=['pdf'])
