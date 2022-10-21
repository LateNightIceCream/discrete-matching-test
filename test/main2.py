import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from itertools import islice, product, zip_longest, combinations
import matplotlib.pyplot as plt
import logging
import os
from enum import Enum
import time
from pprint import pprint
short = rf.data.wr2p2_short
rf.stylely()

class CompKey(Enum):
    SERIES = 1
    SHUNT = 2

class CompType(Enum):
    TRUESERIES  = 1
    TRUESHUNT   = 2
    FALSESERIES = 3
    FALSESHUNT  = 4 # currently unused


# https://stackoverflow.com/questions/69368419/cartesian-product-with-specific-order
def specific_order_cartesian(lists):
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


def get_common_frequency(network_a, network_b):
    small_network = None
    large_network = None

    if network_a.frequency.npoints >= network_b.frequency.npoints:
        large_network = network_a
        small_network = network_b
    else:
        large_network = network_b
        small_network = network_a

    return small_network.frequency.overlap(large_network.frequency)


def get_comp_type_from_dir(dir):
    if not os.path.isdir(dir):
        return None
    end_dir = os.path.basename(os.path.normpath(dir))
    type = None
    if dir.startswith('components/series'):
        type = CompType.TRUESERIES
        if end_dir.startswith('shunt'):
            type = CompType.FALSESERIES
    elif dir.startswith('components/shunt'):
        type = CompType.TRUESHUNT
        if end_dir.startswith('series'):
            type = CompType.FALSESHUNT
    return type


class ComponentPoolEntry():
    def __init__(self, networks = None):
        if networks is None:
            self.networks = []
        else:
            self.networks = networks
        self.length = len(self.networks)
        self.index = 0

    def add_network(self, network):
        self.networks.append(network)
        self.length += 1

    def draw_network_cyclic(self):
        if self.index >= self.length:
            self.index = 0
        result = self.networks[self.index]
        self.index += 1
        return result


# makes the neccessary copies for every component
class ComponentPool():
    def __init__(self, components, network_description):
        self.pool = {} # dictionary where every key is the component's name and the items are ComponentPoolEntry
        self.components = components
        self.network_description = network_description
        self.shunt_copies = 0
        self.series_copies = 0
        self._init_copies()

    def _determine_copy_counts(self):
        for comp_key in self.network_description:
            if comp_key == CompKey.SHUNT:
                self.shunt_copies += 1
            elif comp_key == CompKey.SERIES:
                self.series_copies += 1

    def _init_copies(self):
        self._determine_copy_counts()
        for component in self.components:
            key = self._get_key_from_component(component)
            orig_network = component.network
            num_of_copies = 0
            if component.type == CompType.TRUESHUNT or component.type == CompType.FALSESHUNT:
                num_of_copies = self.shunt_copies
            elif component.type == CompType.TRUESERIES or component.type == CompType.FALSESERIES:
                num_of_copies = self.series_copies

            entry = ComponentPoolEntry()
            print('KEY: ' + key)
            for i in range(0, num_of_copies):
                copied_network = orig_network.copy()
                copied_network.name += '_copy_' + str(i)
                print(copied_network.name)
                entry.add_network(copied_network)
            self.pool[key] = entry


    def _get_key_from_component(self, component):
        return component.network.name

    def draw_network(self, component):
        key = self._get_key_from_component(component)
        return self.pool[key].draw_network_cyclic()


class MatchingComponent():
    def __init__(self, network, type):
        self.network = network
        self.type = type

    def needs_ground(self):
        # idk if falseseries really works or makes sense
        return self.type == CompType.FALSESHUNT or self.type == CompType.FALSESERIES


class MatchingNetworkLibrary():
    def __init__(self, series_dir = None, shunt_dir = None):
        self.components = [] # -> [MatchingComponent]
        self.network_description = None
        self.frequency = None
        self.component_variations = None # iter
        self.number_of_variations = None

        self.components += self._read_all_from_dir('components/series')
        self.components += self._read_all_from_dir('components/shunt')
        self._make_frequencies_common()
        for comp in self.components:
            print(comp.network.frequency)

        self.component_pool = None


    def __iter__(self):
        return self


    def __next__(self):
        # return description + network variation
        #try:
        variation = next(self.component_variations)
        circuit = self._build_circuit(variation)
        #description = self._get_component_variation_description(variation)
        return circuit
        #except:
        #    raise StopIteration


    def _make_frequencies_common(self):
        # little inefficient, was better with NetworkSets but it's ok.
        comb = combinations(self.components, 2)

        common_freq = None
        for comps in comb:
            common_freq = get_common_frequency(comps[0].network, comps[1].network)
            for comp in comps:
                comp.network.interpolate_self(common_freq)

        self.frequency = common_freq


    def _read_all_from_dir(self, dir):
        subdirs = os.listdir(dir)
        all = []
        for subdir in subdirs:
            subpath = os.path.join(dir, subdir)
            comp_type = get_comp_type_from_dir(subpath)
            if comp_type == None:
                continue
            temp_dict = rf.read_all(subpath, contains='s2p')
            for key in temp_dict:
                all.append(MatchingComponent(temp_dict[key], comp_type))
        return all


    def get_components(self, keylist = [CompType.TRUESERIES, CompType.FALSESERIES, CompType.TRUESHUNT, CompType.FALSESHUNT]):
        out = []
        for comp in self.components:
            if comp.type in keylist:
                out.append(comp)
        return out


    def _parse_network_template_description(self, network_description):
        series_components = self.get_components([CompType.TRUESERIES, CompType.FALSESERIES])
        shunt_components = self.get_components([CompType.TRUESHUNT, CompType.FALSESHUNT])
        result = []
        for key in network_description:
            if key == CompKey.SERIES:
                result.append(series_components)
            elif key == CompKey.SHUNT:
                result.append(shunt_components)
        return result


    def _build_circuit(self, variation):
        # TODO: maybe recursion would help?
        input = rf.Circuit.Port(self.frequency, 'Port 1')
        output = rf.Circuit.Port(self.frequency, 'Port 2')
        ground = rf.Circuit.Ground(self.frequency, 'Ground 1')

        connexions = []
        current_connexion = []
        ground_connexion = [(ground, 0)]
        current_connexion = [(input, 0)]

        name_index = 0
        # it's messy but ok
        for component in variation:

            #current_network = component.network.copy()
            #current_network.name += '_copy' + str(name_index) # need to copy and rename because double networks will cause an error with the Circuit constructor
            # current_network = component.network
            # determine if a copy is neccessary, this is actually faster than just copying all by default
            #for con in connexions: # connexions does not contain anything if you start with a shunt!
            #    for net_port_pair in con:
            #        if current_network in net_port_pair:
            #            current_network = component.network.copy()
            #            current_network.name += '_copy' + str(name_index) # need to copy and rename because double networks will cause an error with the Circuit constructor

            # TODO: possible speed improvement:
            # - current problem: network.copy() takes a lot of time
            # - components are copied for _every_ circuit
            # - solution: it is known how many copies are needed at max based on the network_description
            # - create a pool of copies and then draw from the pool when needed instead of using network.copy() here
            # example:
            # network_description = SHUNT, SHUNT, SERIES, SERIES
            # --> in a single variation / circuit, at max two networks can be identical (same component)
            # --> so e.g. num of copies of all shunt comps = num of SHUNT occurences in network_description
            # same for series
            # idea: current_network = self.component_pool.draw_network(component)
            # and you wouldnt need to check if it is already in the connexion
            #for net_port_pair in current_connexion:
            #    if current_network.name == net_port_pair[0].name:
            #        current_network = component.network.copy()
            # current_network.name += '_copy' + str(name_index) # need to copy and re

            current_network = self.component_pool.draw_network(component)

            if component.type == CompType.TRUESERIES or component.type == CompType.TRUESHUNT:
                current_connexion.append((current_network, 0))
                connexions.append(current_connexion) # terminate current connexion
                current_connexion = [] # create a new connexion
                current_connexion.append((current_network, 1))

            if component.needs_ground():
                current_connexion.append((current_network, 0))
                ground_connexion.append((current_network, 1))

            name_index += 1

        current_connexion.append((output, 0))
        connexions.append(current_connexion)

        if len(ground_connexion) > 1:
            connexions.append(ground_connexion)

        try:
            result = rf.Circuit(connexions)
        except:
            logging.error("--------------------------")
            logging.error('error while trying to create rf.Circuit from connexions')
            logging.error("--------------------------")
            for con in connexions:
                print(con)
            return None

        #result.plot_graph(network_labels = True, port_labels = True)
        #save_all_figs('./plots', format=['pdf'])
        return result

    def _init_component_pool(self):
        self.component_pool = ComponentPool(self.components, self.network_description)


    def init_network_variations(self, network_description):
        self.network_description = network_description
        variation_template = self._parse_network_template_description(network_description)
        self.component_variations = iter(specific_order_cartesian(variation_template))
        #self._build_circuit(list(self.component_variations)[2353])


    def adjust_to_network(self, network):
        freq = get_common_frequency(self.components[0].network, network)
        self.components[0].network.frequency = freq
        self._make_frequencies_common()
        self._init_component_pool() # oh well
        return freq


def main():
    mcl = MatchingNetworkLibrary()
    mcl.init_network_variations([CompKey.SHUNT, CompKey.SERIES, CompKey.SHUNT, CompKey.SERIES])

    antenna = rf.Network('antenna/ellio-raw.s1p')
    freq = mcl.adjust_to_network(antenna)
    #antenna.interpolate_self(freq)


    circ = None
    i = 0
    for circuit in mcl:
        i += 1
        if i == 2004:
            circ = circuit
            break

    matchnet = circ.network

    '''
    start = time.time()
    i = 0
    # raw: 200sec
    for circuit in mcl:
        #out.append(circuit)
        if (i % 1000 == 0):
            print(i)
        i += 1
        pass
        #print(circuit, end="\r")

    end = time.time()
    print(end-start)
    '''

if __name__ == '__main__':
    main()
