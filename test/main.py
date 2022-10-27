import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs
import matplotlib.pyplot as plt
import logging
import os
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
import time
import csv
from matchingsim import *
import winsound

short = rf.data.wr2p2_short
rf.stylely()

csvdata = []

class MyEvaluator(Evaluator):
    def __init__(self):
        self.best_max = 0

    def evaluate(self, data):
        '''
        return data if 'optimal'
        else return None
        data[0]: index
        data[1]: network
        data[2]: variation
        '''

        (i, network, variation) = data

        f_2_l = '1700mhz'
        f_2_h = '1900mhz'
        range_2 = f_2_l + '-' + f_2_h

        s11_2 = rf.mathFunctions.complex_2_db(network[range_2].s11.s)

        maxdb_2 = max(s11_2)
        mindb_2 = min(s11_2)

        csvdata.append((i, maxdb_2, mindb_2))

        #print(i)

        if (mindb_2 < -7 and maxdb_2 < -3):
            if (maxdb_2 < self.best_max):
                self.best_max = maxdb_2
                print(maxdb_2)
                print(mindb_2)
                return data
        return None

    def get_result_str(self, data):
        (i, network, variation) = data
        out = ''
        out += ('Result @ %sth iteration:' % (str(i))) + '\n'
        for component in variation:
            out += (component.name) + '\n'
        return out

def plot_results(final_res, results):

    figure(0)
    (i, network, variation) = final_res
    network._plot_s_db(title='best')

    figure(1)
    for result in results:
        (i, network, variation) = data
        network.plot_s_db()

    save_all_figs('./plots', format=['pdf'])

def print_simulation_result(data, time):
    secs = time
    mins = time / 60
    hours = mins / 60
    logging.info('===================')
    logging.info('Simulation finished in %s seconds (= %s min = %s hours)' % (str(secs), str(mins), str(hours)))
    logging.info('===================')

    (i, network, variation) = data

    logging.info('Optimal Result @ %sth iteration' % (str(i)))
    for component in variation:
        logging.info(component.name)

    logging.info('===================')


def main():
    antenna = rf.Network('antenna/20221027-ellio-raw.s1p')

    evaluator = MyEvaluator()

    network_description = [CompKey.SERIES, CompKey.SHUNT, CompKey.SERIES, CompKey.SHUNT]

    simManager = MatchingSimulationManager(antenna, evaluator, network_description)

    start = time.time()
    (final_result, feasible_results) = simManager.simulate()
    end = time.time()

    with open(r'test.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['i', 'max', 'min'])
        for dat in csvdata:
            (i, max, min) = dat
            writer.writerow([i, max, min])

    if not final_result:
        logging.warning('no solutions were found with the given evaluator!')
        return

    print_simulation_result(final_result, end - start)
    (i, network, variation) = final_result

    plot_results(final_result, feasible_results)

    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)

if __name__ == '__main__':
    main()
