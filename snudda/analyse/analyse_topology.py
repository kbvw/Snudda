import os
import numpy as np

from snudda.utils.load import SnuddaLoad
from snudda.utils.load_network_simulation import SnuddaLoadNetworkSimulation
from snudda.utils.export_connection_matrix import SnuddaExportConnectionMatrix
from collections import OrderedDict


class SnuddaAnalyseTopology:

    """ Analyses the topology, and the effect of topology """

    def __init__(self, network_file):

        self.network_file = network_file
        self.snudda_load = SnuddaLoad(network_file=network_file)
        self.simulation_data = dict()
        self.simplex_data = dict()

        secm = SnuddaExportConnectionMatrix(in_file=self.network_file, out_file="dummy_file", save_on_init=False)
        self.connection_matrix = secm.create_connection_matrix()

    def load_simplex_file(self, simplex_file_name):
        data = np.loadtxt(simplex_file_name, dtype=int)
        simplex_dimension = data.shape[1] - 1
        self.simplex_data[simplex_dimension] = data

        print(f"Loaded simplex data of dimension {simplex_dimension} from {simplex_file_name}")

    def load_simulation_data(self, data_key, simulation_output=None):
        self.simulation_data[data_key] = SnuddaLoadNetworkSimulation(network_path=os.path.dirname(self.network_file),
                                                                     network_simulation_output_file=simulation_output)

    def check_same_neurons(self, data_key_A, data_key_B):

        sim_A = self.simulation_data[data_key_A]
        sim_B = self.simulation_data[data_key_B]

        is_same = len(list(sim_A.iter_neuron_id())) == len(list(sim_B.iter_neuron_id()))

        for nid_A, nid_B in zip(sim_A.iter_neuron_id(), sim_B.iter_neuron_id()):
            is_same = is_same and nid_A == nid_B
            is_same = is_same and sim_A.get_neuron_keys(nid_A) == sim_B.get_neuron_keys(nid_B)

        return is_same

    def compare_spike_times(self, data_key_A, data_key_B):

        # Check that the neurons compared are the same (by verifying parameter key, morphology key, modulation key)
        assert self.check_same_neurons(data_key_A, data_key_B), f"data_keys have different neurons in the network"

        # Match spikes against each other, compute change...

        sim_A = self.simulation_data[data_key_A]
        sim_B = self.simulation_data[data_key_B]

        spikes_A = sim_A.get_spikes()
        spikes_B = sim_B.get_spikes()

        for neuron_id in spikes_A.keys():
            s_a = spikes_A[neuron_id]
            s_b = spikes_B[neuron_id]

            t_diff = np.kron(s_a, np.ones(s_b.T.shape)) - np.kron(np.ones(s_a.shape), s_b.T)
            min_pos = np.argmin(np.abs(t_diff), axis=0)
            t_min_diff = [t_diff[m[0], m[1]] for m in zip(min_pos, range(len(min_pos)))]

            import pdb
            pdb.set_trace()

    def verify_source_sink_order(self):

        for dim in self.simplex_data.keys():
            print(f"Verifying dimension {dim}")
            ctr = 0
            for simplex in self.simplex_data[dim]:
                sub_connection_matrix = self.connection_matrix[simplex, :][:, simplex]
                try:
                    assert (sub_connection_matrix[0, 1:] > 0).all(), f"First element not source in simplex {simplex}"
                    assert (sub_connection_matrix[:-1, -1] > 0).all(), f"Last element not sink in simplex {simplex}"
                except:
                    import traceback
                    print(traceback.format_exc())
                    import pdb
                    pdb.set_trace()
                ctr += 1
            print(f"Verified {ctr} simplices")

    def get_multiplicity(self):

        multiplicity = OrderedDict()

        for dim in self.simplex_data.keys():
            mult_dict = dict()
            for simplex in self.simplex_data[dim]:
                idx = tuple(np.sort(simplex))
                if idx not in mult_dict:
                    mult_dict[idx] = 1
                else:
                    mult_dict[idx] += 1

            multiplicity[dim] = mult_dict

        return multiplicity

    def get_fixed_multiplicity(self):

        multiplicity = OrderedDict()

        for dim in self.simplex_data.keys():
            mult_dict = dict()
            for simplex in self.simplex_data[dim]:
                simplex_copy = simplex.copy()
                simplex_copy[1:-1].sort()  # Sorts the part of the array in place, wow!
                idx = tuple(simplex_copy)
                if idx not in mult_dict:
                    mult_dict[idx] = 1
                else:
                    mult_dict[idx] += 1

            multiplicity[dim] = mult_dict

        return multiplicity

    def get_fixed_multiplicity_ALT(self):

        multiplicity = OrderedDict()

        for dim in self.simplex_data.keys():
            mult_dict = dict()
            for simplex in self.simplex_data[dim]:
                simplex_copy = simplex.copy()
                simplex_copy[1:-1].sort()  # Sorts the part of the array in place, wow!
                idx = tuple(simplex_copy)
                if idx not in mult_dict:
                    mult_dict[idx] = [1, [simplex]]
                else:
                    mult_dict[idx][0] += 1
                    mult_dict[idx][1].append(simplex)

            multiplicity[dim] = mult_dict

        return multiplicity

    def filter_multiplicity(self, multiplicity, dimension, neuron_type_list, multiplicity_requirement=None):

        """

        Args:
            multiplicity (OrderedDict) : Multiplicity dictionary
            dimension (int) : Dimension of data to look at
            neuron_type_list (list) : Filtering information, e.g. [('FS', 2), ('dSPN', 1)] means that
                                      only cliques that contain exactly 2 FS and 1 dSPN are kept
            multiplicity_requirement (int) : Multiplicity of the simplex kept, default = None (no filtering)

        Returns:
            filtered_multiplicity (OrderedDict) : Only returns dimension data
                                  """

        filtered_multiplicity = OrderedDict()

        for neurons_key, mult in multiplicity[dimension].items():
            neuron_types = [self.snudda_load.data["neurons"][x]["type"] for x in neurons_key]

            keep_simplex = True if multiplicity_requirement is None else mult == multiplicity_requirement

            for neuron_type, neuron_type_number in neuron_type_list:
                if np.sum([neuron_type == x for x in neuron_types]) != neuron_type_number:
                    keep_simplex = False

            if keep_simplex:
                filtered_multiplicity[neurons_key] = mult

        return filtered_multiplicity

    def print_multiplicity(self, fixed=True):

        if fixed:
            # Fix source and sink in the ordering
            multiplicity = self.get_fixed_multiplicity()
        else:
            multiplicity = self.get_multiplicity()

        for dim in multiplicity.keys():
            print(f"-- Analysing dimension {dim}")
            #import pdb
            #pdb.set_trace()
            repeats = np.bincount(np.array([x for x in multiplicity[dim].values()]))
            for reps, count in enumerate(repeats):
                if count > 0:
                    print(f"Multiplicity {reps} for {count} simplices")

            print("")
        import pdb
        pdb.set_trace()


if __name__ == "__main__":

    from argparse import ArgumentParser

    parser = ArgumentParser(description="Load snudda network file (hdf5)")
    parser.add_argument("network_file", help="Network file (hdf5)", type=str)
    parser.add_argument("simplex_files", nargs="*", action="append", type=str)

    args = parser.parse_args()

    at = SnuddaAnalyseTopology(network_file=args.network_file)
    for simplex in args.simplex_files[0]:
        at.load_simplex_file(simplex)

    at.verify_source_sink_order()
    at.print_multiplicity(fixed=True)

    import pdb
    pdb.set_trace()