import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from scipy.optimize import minimize
import numpy as np
import matplotlib.pyplot as plt
from enum import Enum
from itertools import islice, product, zip_longest, combinations, repeat
import math
from multiprocessing import Pool
import time

class CompKey(Enum):
    SERIES = 1
    SHUNT = 2

class CompType(Enum):
    CAPACITOR = 1
    INDUCTOR = 2


Z_0 = 50
antenna = rf.Network('test/antenna/ellio-raw-22nH-shunt.s1p')
lte = rf.Network('test/bp_LTE.s1p')

# frequency band centered on the frequency of interest
frequency = antenna.frequency
# transmission line Media
line = rf.DefinedGammaZ0(frequency=frequency, z0=Z_0)
# load Network

Nfeval = 1

class Component:
    def __init__(self, netfun, initial_value, bounds, factor):
        self.netfun = netfun
        self.initial_value = initial_value
        self.bounds = bounds
        self.factor = factor

def parse_network_template_description(network_description):
    cap_bounds = (1e-12, 10e3)
    cap_bounds_shunt = (1e-12, 10e3)
    ind_bounds = (1e-12, 10e3)
    cap_initial = 1.5
    ind_initial = 1
    series_cap = Component(line.capacitor, cap_initial, cap_bounds, 1e-12)
    series_ind = Component(line.inductor, ind_initial, ind_bounds, 1e-9)
    shunt_cap  = Component(line.shunt_capacitor, cap_initial, cap_bounds_shunt, 1e-12)
    shunt_ind  = Component(line.shunt_inductor, ind_initial, ind_bounds, 1e-9)
    series_components = [series_cap, series_ind]
    shunt_components = [shunt_cap, shunt_ind]
    result = []
    for key in network_description:
        if key == CompKey.SERIES:
            result.append(series_components)
        elif key == CompKey.SHUNT:
            result.append(shunt_components)
    return result


# https://stackoverflow.com/questions/69368419/cartesian-product-with-specific-order
def _specific_order_cartesian(lists):
    its = [[lst[0]] for lst in lists]
    yield tuple(lst[0] for lst in lists)

    for column in list(islice(zip_longest(*lists), 1, None)):
        for i, p in reversed(list(enumerate(column))):
            if p is None:
                continue

            yield from product(
                *(
                    (p,) if j == i else its[j]
                    for j in range(len(lists))
                )
            )

            its[i].append(p)

def printx(Xi):
    global Nfeval
    global fout
    print('At iterate {0:4d}'.format(Nfeval) + '\n')
    Nfeval += 1


def matching_network(variation):
    def network(*args):
        net = variation[0].netfun(args[0] * variation[0].factor)
        i = 1
        for comp in variation[1:]:
            netfun = comp.netfun
            net = net ** netfun(args[i] * comp.factor)
            i += 1
        return net ** antenna
    return network

def get_starting_values(variation):
    starting_vals = ()
    for comp in variation:
        starting_vals = starting_vals + (comp.initial_value,)
    return starting_vals


def get_bounds(variation):
    bounds = ()
    for comp in variation:
        bounds = bounds + (comp.bounds,)
    return bounds


def objective_function(matching_net):
    def obj_fun(*args):
        _ntw = matching_net(*args)
        range1 = '791mhz-861mhz'
        range2 = '1710mhz-1880mhz'
        max_db_1 = max(rf.mathFunctions.complex_2_db(_ntw[range1].s11.s))[0][0]
        max_db_2 = max(rf.mathFunctions.complex_2_db(_ntw[range2].s11.s))[0][0]
        return -1 * max_db_1 * max_db_2
    return obj_fun


def objective_function_2(variation):
    def obj_fun(*args):
        net = variation[0].netfun(args[0][0] * variation[0].factor)
        i = 1
        for comp in variation[1:]:
            netfun = comp.netfun
            net = net ** netfun(args[0][i] * comp.factor)
            i += 1
        _ntw = net ** antenna

        range1 = '791mhz-861mhz'
        range2 = '1710mhz-1880mhz'
        max_db_1 = max(rf.mathFunctions.complex_2_db(_ntw[range1].s11.s))[0][0]
        max_db_2 = max(rf.mathFunctions.complex_2_db(_ntw[range2].s11.s))[0][0]
        return -1 * max_db_1 * max_db_2

    return obj_fun


def objective_function_3(variation):
    def obj_fun_loc(*args):
        net = variation[0].netfun(args[0][0] * variation[0].factor)
        i = 1
        for comp in variation[1:]:
            netfun = comp.netfun
            net = net ** netfun(args[0][i] * comp.factor)
            i += 1
        _ntw = net ** antenna

        range1 = '791mhz-861mhz'
        range2 = '1710mhz-1880mhz'
        max_db_1 = max(rf.mathFunctions.complex_2_db(_ntw[range1].s11.s))[0][0]
        max_db_2 = max(rf.mathFunctions.complex_2_db(_ntw[range2].s11.s))[0][0]
        min_db_1 = min(rf.mathFunctions.complex_2_db(_ntw[range1].s11.s))[0][0]
        min_db_2 = min(rf.mathFunctions.complex_2_db(_ntw[range2].s11.s))[0][0]

        return max_db_2 + max_db_1

    return obj_fun_loc


def sim_thread(variation):
    matching_net = matching_network(variation)
    x0 = get_starting_values(variation)
    bound = get_bounds(variation)
    res1 = minimize(objective_function_3(variation), x0, bounds=bound)#, callback = printx)
    ntw1 = matching_net(*res1.x)
    print(ntw1)
    print('------------')
    for comp in variation:
        print(comp.netfun)
    print(res1.x)
    print('------------')
    ntw1.plot_s_db(lw=2)
    return res1


def simulate(variations):
    p = Pool()
    result = p.map(sim_thread, variations)
    for res in result:
        print(res)
    #
    #for variation in variations:
    #    result = sim_thread(variation)

if __name__ == '__main__':
    start_time = time.time()
    network_description = [CompKey.SERIES, CompKey.SHUNT, CompKey.SERIES]
    variation_template = parse_network_template_description(network_description)
    variations = _specific_order_cartesian(variation_template)
    simulate(variations)
    lte.plot_s_db(lw=2)
    save_all_figs('./plots', format=['pdf'])
    end_time = time.time()

    print('--- finished in %s seconds ---' % (str(end_time - start_time)))
