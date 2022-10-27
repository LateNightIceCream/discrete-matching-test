import skrf as rf
from skrf.data import ring_slot
from skrf.plotting import save_all_figs

comp1 = rf.Network('components\shunt\series_L\LQW15AN1N5C80_series.s2p')
comp2 = rf.Network('components\shunt\series_L\LQW15AN2N2B80_series.s2p')

freq = comp1.frequency
print(freq)
media = rf.DefinedGammaZ0(freq)
short = media.short()
print(short)

network = rf.connect(comp1, 1, comp2, 0)
network = rf.connect(comp2, 1, short, 0)
network = rf.network.one_port_2_two_port(network)


#q.plot_graph(network_labels = True, port_labels = True)
network.plot_s_db()
save_all_figs('./plots', format=['pdf'])
