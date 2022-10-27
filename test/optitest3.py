import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from scipy.optimize import minimize
import numpy as np
import matplotlib.pyplot as plt

Z_L = 200 - 100j
Z_0 = 50
f_0_str = '500MHz'


component = rf.Network('components/series/C/R07S0R5-H-SER.s2p')['500mhz-4000mhz']

C_nom = 0.5 # pF

'''
             R_p
           --^^^--
L_s   Rs   |  C   |
====--^^^--*--||--*---
           |      |
           -^^^-||-
            RDA CDA
'''

# frequency band centered on the frequency of interest
frequency = component.frequency
line = rf.DefinedGammaZ0(frequency=frequency, z0=Z_0)

orig = component ** line.short()

def cap_network(L_s, R_s, R_p, C = C_nom):
    l_s = L_s * 1e-9
    cda = CDA * 1e-12
    c = C_nom * 1e-12
    return line.inductor(l_s) ** line.resistor(R_s) ** line.shunt(line.resistor(R_p) **line.short()) ** line.shunt_capacitor(c) ** line.open()

# initial guess values
L_s_0 = 1 # nH
R_s_0 = 0.001
R_p_0 = 1000000
RDA = 100
CDA = 0.1
x0 = (L_s_0, R_s_0, R_p_0, C_nom)
# bounds
L_s_minmax = (1, 100) #nH
R_s_minmax = (0, 10)
R_p_minmax = (10000, 10000000000)
RDA_minmax = (0, 1000000) #nH
CDA_minmax = (0, C_nom) # pF
C_nom_minmax = (C_nom/3, C_nom*3) # pF

def objective_function_1(x):
    _ntw = cap_network(*x)
    differences = orig.s_mag - _ntw.s_mag
    squares = np.square(differences)
    sum_of_squares = np.sum(squares)
    return sum_of_squares


res1 = minimize(objective_function_1, x0, bounds=(L_s_minmax, R_s_minmax, R_p_minmax, C_nom_minmax))

print('DONE!')

ntw1 = cap_network(*res1.x)
print(res1.x)

ntw1.plot_s_db(lw=2, label='parasitic optimization test')
orig.plot_s_db(lw=2, label='original')
save_all_figs('./plots', format=['pdf'])
