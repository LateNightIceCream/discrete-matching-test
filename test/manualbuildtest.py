
import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from scipy.optimize import minimize
import numpy as np
import matplotlib.pyplot as plt
from itertools import islice, product, zip_longest, combinations, repeat

antenna = rf.Network('antenna/ellio-raw.s1p')
comp1 = rf.Network('components/shunt/series_L/LQW15AN1N5C80_series.s2p')
comp2 = rf.Network('components/series/L/LQW15AN1N5C80.s2p')
comp3 = rf.Network('components/shunt/C/R07S0R7_SNT.s2p')

frequency = antenna.frequency

comp1.interpolate_self(frequency)
comp2.interpolate_self(frequency)
comp3.interpolate_self(frequency)

line = rf.DefinedGammaZ0(frequency=frequency, z0=50)

full_net = comp1 ** line.short()
full_net = line.shunt(comp1 ** line.short())
full_net = line.shunt(comp1 ** line.short()) ** comp2 ** antenna
full_net = line.shunt(comp1 ** line.short()) ** comp2 ** comp3

full_net = full_net ** antenna

print(full_net['1.4ghz'].s_db)


full_net.plot_s_db(label='LC network 1')
save_all_figs('./plots', format=['pdf'])
