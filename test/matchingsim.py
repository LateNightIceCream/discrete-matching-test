import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from skrf.data import wr2p2_short as short
from itertools import islice, product, zip_longest, combinations, repeat
import matplotlib.pyplot as plt
import logging
import os
from enum import Enum
import time
from pprint import pprint
import concurrent.futures
from multiprocessing import Pool
import concurrent.futures
from more_itertools import ichunked

USE_MULTIPROCESSING = True

class CompKey(Enum):
    SERIES = 1
    SHUNT = 2


class CompType(Enum):
    TRUESERIES  = 1
    TRUESHUNT   = 2
    FALSESERIES = 3
    FALSESHUNT  = 4 # currently unused (doesnt really make sense anyway)


class Evaluator():
    def __init__(self):
        pass

    def evaluate(self, data):
        '''
        return data if 'optimal'
        else return None
        data[0]: index
        data[1]: network
        data[2]: variation
        '''
        i, network, variation = data
        return data

    def get_result_str(self, data):
        return 'please implement the get_result_str() function in your Evaluator'

    def print_result(self, data):
        logging.info(self.get_result_str(data))
        logging.info('===================')


class MatchingSimulationManager():
    def __init__(self, dut, evaluator, network_description):
        self.network_library = MatchingNetworkLibrary()
        self.evaluator = evaluator
        self.dut = dut
        self.network_library.init_network_variations(network_description, dut)
        self.dut.interpolate_self(self.network_library.frequency)


    def sim_thread(self, i, network, variation):
        #self._overlap_dut_and_network(network)
        #(self.dut, network) = rf.network.overlap(self.dut, network)
        try:
            result_network = network ** self.dut
        except:
            logging.error('--------------')
            logging.error('error in simulation thread!')
            logging.error('details: ')
            logging.error('Iteration number: ' + str(i))
            logging.error('network frequency:')
            logging.error(network.frequency)
            logging.error('DUT frequency:')
            logging.error(self.dut.frequency)
            logging.error('--------------')
            result_network = None

        return (i, result_network, variation)


    def simulate(self):
        i = 0
        simulation_result = None
        all_feasible_results = []
        for (network, variation) in self.network_library:
            #network = circuit.network # BOTTLENECK!
            data = (i, network, variation)
            res_data = self.sim_thread(i, network, variation)
            ev_result = self.evaluator.evaluate(res_data)
            if ev_result != None:
                self.evaluator.print_result(ev_result)
                simulation_result = ev_result
                all_feasible_results.append(simulation_result)

            if i % 100 == 0:
                logging.info('progress: ' + str(i))
            i += 1

        return (simulation_result, all_feasible_results)


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
            #print('KEY: ' + key)
            for i in range(0, num_of_copies):
                copied_network = orig_network.copy()
                copied_network.name += '_copy_' + str(i)
                #print(copied_network.name)
                entry.add_network(copied_network)
            self.pool[key] = entry


    def _get_key_from_component(self, component):
        return component.network.name

    def draw_network(self, component):
        key = self._get_key_from_component(component)
        return self.pool[key].draw_network_cyclic()


class MatchingComponent():
    def __init__(self, network, type, name):
        self.network = network
        self.type = type
        self.name = name

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

        self.component_pool = None

        self.line = None


    def __iter__(self):
        return self


    def __next__(self):
        # return description + network variation
        #try:
        variation = next(self.component_variations)
        #circuit = self._build_circuit(variation)
        network = self._build_network(variation)
        #description = self._get_component_variation_description(variation)
        return (network, variation) ### circuit.network for testing, takes very long?
        #except:
        #    raise StopIteration


    def _make_frequencies_common(self, dut = None):
        # little inefficient, was better with NetworkSets but it's ok.
        common_freq = None
        # inject dut (hacky way)
        if dut:
            self.components.append(MatchingComponent(dut, CompType.TRUESERIES, 'antenna'))

        network_a = None
        network_b = None
        combs = combinations(self.components, 2)
        for components in combs:
            network_a = components[0].network
            network_b = components[1].network

            if network_a.frequency.npoints >= network_b.frequency.npoints:
                large_network = network_a
                small_network = network_b
            else:
                large_network = network_b
                small_network = network_a

            (components[0].network, components[1].network) = rf.network.overlap(large_network, small_network)

        self.frequency = network_b.frequency # hack! TODO: figure out right network network_b or network_a to assign to self.frequency dynamically
        self.components.pop()


    def _read_all_from_dir(self, dir):
        subdirs = os.listdir(dir)
        all = []
        for subdir in subdirs:
            subpath = os.path.join(dir, subdir)
            comp_type = _get_comp_type_from_dir(subpath)
            if comp_type == None:
                continue
            temp_dict = rf.read_all(subpath, contains='s2p')
            for key in temp_dict:
                all.append(MatchingComponent(temp_dict[key], comp_type, name=key))
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


    # alternative to _build_circuit() because circuit.network is slow
    def _build_network(self, variation):
        short = self.line.short()
        resulting_network = None
        started = False
        # just hacked rn TODO: clean it up
        for component in variation:
            current_network = self.component_pool.draw_network(component)
            if not started:

                if component.needs_ground():
                    resulting_network = self.line.shunt(current_network ** self.line.short())
                else:
                    resulting_network = current_network
                started = True

            else:
                if component.needs_ground():
                    resulting_network = resulting_network ** self.line.shunt(current_network ** self.line.short()) # creates a tee where one port goes to ground
                else:
                    resulting_network = resulting_network ** current_network

        return resulting_network


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
            # - network.copy() takes a lot of time and memory
            # - components are copied for _every_ circuit
            # - solution: it is known how many copies are needed at max based on the network_description
            # - create a pool of copies and then draw from the pool when needed instead of using network.copy() here

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
        return result


    def _init_component_pool(self):
        self.component_pool = ComponentPool(self.components, self.network_description)


    def init_network_variations(self, network_description, dut = None): # TODO: rename
        self.network_description = network_description
        self._make_frequencies_common(dut)
        self.line = rf.DefinedGammaZ0(frequency=self.frequency, z0=50)

        for comp in self.components:
            print(comp.network.frequency)

        self._init_component_pool()
        variation_template = self._parse_network_template_description(network_description)
        self.component_variations = iter(_specific_order_cartesian(variation_template))


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


def _get_comp_type_from_dir(dir):
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
