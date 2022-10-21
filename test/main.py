import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
from itertools import islice, product, zip_longest
import matplotlib.pyplot as plt
import logging
import os
from enum import Enum
short = rf.data.wr2p2_short
rf.stylely()

class CompKey(Enum):
    SERIES = 1
    SHUNT = 2

class CompType(Enum):
    TRUESERIES = 1
    TRUESHUNT = 2
    FALSESERIES = 3
    FALSESHUNT = 4 # currently unused

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


def make_network_sets_frequencies_common(network_sets):
    # could also use cartesian product of all networks
    common_net = network_sets[0][0].copy()
    for network_set in network_sets:
        #for network in network_set:
        first_network = network_set[0]
        common_net.frequency = get_common_frequency(common_net, first_network)

    common_freq = common_net.frequency

    for network_set in network_sets:
        for network in network_set:
            network.interpolate_self(common_freq)


class MatchingComponentNetworkSet():
    def __init__(self, network_set, type):
        self.network_set = network_set
        self.type = type


class MatchingComponents():
    def __init__(self, series_dir, shunt_dir):
        self.component_dict = {
            CompKey.SERIES: None, # -> NetworkSet
            CompKey.SHUNT: None, # -> NetworkSet
            CompKey.FALSESERIES: None,
            CompKey.FALSESHUNT: None,
        }

        self.component_dict = {
            CompKey.SERIES: {
                CompType.TRUESERIES: None # -> [MatchingComponentNetwork]
                CompType.FALSESERIES: None, # -> NetworkSet
            },
            CompKey.SHUNT: {
                CompType.TRUESHUNT: None # -> NetworkSet
                CompType.FALSESHUNT: None, # -> NetworkSet
            },
        }


        self.series_dir = series_dir
        self.shunt_dir  = shunt_dir
        self.frequency = None

        self._read_all_components()


    def _read_all_components(self):
        if not os.path.isdir(self.series_dir):
            logging.error('directory not found: ' + self.series_dir)
            return
        if not os.path.isdir(self.shunt_dir):
            logging.error('directory not found: ' + self.shunt_dir)
            return

        self.component_dict[CompKey.SERIES] = self._read_all_from_dir(self.series_dir)
        self.component_dict[CompKey.SHUNT] = self._read_all_from_dir(self.shunt_dir)
        make_network_sets_frequencies_common([self.component_dict[CompKey.SERIES], self.component_dict[CompKey.SHUNT]])
        self.frequency = self.component_dict[CompKey.SERIES][0].frequency


    def _read_networkset_from_dir(self, dir) -> rf.NetworkSet:
        if not os.path.isdir(dir):
            logging.warning('not a directory: ' + str(dir))
            return None
        temp_dict = rf.read_all(dir, contains='s2p')
        networkset = rf.NetworkSet(temp_dict)
        return networkset


    def _read_all_from_dir(self, dir) -> rf.NetworkSet:
        '''
        merges all subdir s2p files into a single NetworkSet
        with common frequency by interpolation
        '''
        subdirs = os.listdir(dir)
        networksets = []
        for subdir in subdirs:
            ns = self._read_networkset_from_dir(os.path.join(dir, subdir))
            if not ns:
                continue
            networksets.append(ns)

        make_network_sets_frequencies_common(networksets)

        z = {}
        for ns in networksets:
            z = z | ns.to_dict()

        result_ns = rf.NetworkSet(z)

        return result_ns


class MatchingNetwork():
    def __init__(self, components, network_description):
        self.network_description = network_description
        self.components = components
        self.series_component_list = list(self.components.component_dict[CompKey.SERIES].to_dict().values())
        self.shunt_component_list = list(self.components.component_dict[CompKey.SHUNT].to_dict().values())
        self.parsed_network_description = self._parse_network_template_description()
        self.component_variations = self._get_component_variations()

    def __next__(self):
        # return description + network variation
        try:
            variation = next(self.component_variations)
            network = self._get_network_from_component_variation(variation)
            description = self._get_component_variation_description(variation)
            return (description, network)
        except:
            raise StopIteration

    def _get_network_from_component_variation(self, comp_variation):
        '''
        returns the combined network
        '''
        return rf.cascade_list(comp_variation)

    def _get_component_variation_description(self, variation):
        # TODO: add if component is series or shunt
        descr = ''
        for network in variation:
            descr += network.name + ', '
        return descr

    # next(mn) ** antenna

    def _get_component_variations(self):
        # TODO: maybe use generator (cartesian function returns generator)
        variations = iter(specific_order_cartesian(self.parsed_network_description))
        return variations

    def _build_circuit(self, variation):
        pass

    def _parse_network_template_description(self):
        result = []
        for compkey in self.network_description:
            # result.append(self.components.component_dict[compkey].to_dict().values())
            if compkey == CompKey.SERIES:
                result.append(self.series_component_list)
            elif compkey == CompKey.SHUNT:
                result.append(self.series_component_list)
            else:
                logging.error('component key "%s" is none of %s' % (compkey, '[CompKey.SERIES, CompKey.SHUNT]'))
                return
        return result

        
def main():
    mc = MatchingComponents('components/series', 'components/shunt')
    mn = MatchingNetwork(mc, [CompKey.SERIES, CompKey.SHUNT, CompKey.SERIES, CompKey.SHUNT])

    print('-----------')
    print('overlapped frequency range of your components: ')
    print(mc.component_dict[CompKey.SERIES][0].frequency)
    print(mc.component_dict[CompKey.SHUNT][0].frequency)
    print(mc.component_dict[CompKey.SERIES][-1].frequency)
    print(mc.component_dict[CompKey.SHUNT][-1].frequency)

    descr, network = next(mn)
    print(descr)
    network.plot_s_db(0,0)
    save_all_figs('./plots', format=['pdf'])
    #plt.title('Big ole Smith Chart')

    #print(type(next(iter(mc.component_dict[CompKey.SHUNT].to_dict()))))
    #print(type(mc.component_dict[CompKey.SHUNT]))
    #print(type(mc.component_dict[CompKey.SHUNT].to_dict().values()))
    #print(mc.component_dict[CompKey.SERIES][-1][-1].frequency)
    #print(mc.component_dict[CompKey.SERIES][-1][-1].frequency)



print(list(specific_order_cartesian(
    #[['x', 'b', 'c'], ['x', 'y'], ['x', 'y']]
    [['x', 'y']]
)))

# goal:
# list(specific_order_cartesian(
#    mc.component_dict['series'], mc.component_dict['shunt'], mc.component_dict['series'], mc.component_dict['shunt'])
# --> iterator
#)

if __name__ == '__main__':
    main()
