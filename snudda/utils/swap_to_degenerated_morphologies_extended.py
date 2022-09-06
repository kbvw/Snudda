import numpy as np

from snudda import SnuddaLoad
from snudda.utils.swap_to_degenerated_morphologies import SwapToDegeneratedMorphologies


class SwapToDegeneratedMorphologiesExtended(SwapToDegeneratedMorphologies):

    def __init__(self, original_network_file, updated_network_file, output_network_file,
                 original_snudda_data_dir, updated_snudda_data_dir,
                 original_input_file=None, updated_input_file=None, output_input_file=None,
                 filter_axon=True
                 ):

        """
            Args:
                original_network_file : Original network-synapses.hdf5 (e.g. network with WT morphologies)
                updated_network_file : network-synapses.hdf5 network with updated morphologies (e.g. Parkinson network)
                output_network_file : Created network-synapses.hdf5 network by this code
                original_snudda_data_dir : Path to original data (e.g. WT SNUDDA_DATA)
                updated_snudda_data_dir : Path to updated data (e.g. Parkinson SNUDDA_DATA)
                original_input_file : Input to original network (e.g. WT network input)
                updated_input_file : Input to the updated_network_file network
                output_input_file: Input file generated by this code (great name!)
                filter_axon : Degeneration of axon leads to removal of synapses

        """

        super().__init__(original_network_file=original_network_file,
                         new_network_file=output_network_file,
                         original_snudda_data_dir=original_snudda_data_dir,
                         new_snudda_data_dir=updated_snudda_data_dir,
                         original_input_file=original_input_file,
                         new_input_file=output_input_file, filter_axon=filter_axon)

        self.updated_network_file = updated_network_file
        self.updated_network_loader = SnuddaLoad(self.updated_network_file, load_synapses=False)
        self.updated_hdf5 = self.updated_network_loader.hdf5_file
        self.updated_data = self.updated_network_loader.data

        self.old_kd_tree_cache = dict()
        self.old_neuron_cache_id = dict()

        self.check_same_network()

    def check_same_network(self):

        assert len(self.original_network_loader.data["neurons"]) == len(self.updated_network_loader.data["neurons"]),\
            f"Original and updated network does not have the same number of neurons!"

        for orig_neuron, updated_neuron in zip(self.original_network_loader.data["neurons"],
                                               self.updated_network_loader.data["neurons"]):

            assert orig_neuron["neuronID"] == updated_neuron["neuronID"], f"Internal error, neuron ID mismatch"

            assert orig_neuron["name"] == updated_neuron["name"], \
                f"Name mismatch for neuron {orig_neuron['neuronID']}: {orig_neuron['name']} {updated_neuron['name']}"

            assert (orig_neuron["position"] == updated_neuron["position"]).all(), \
                f"Position mismatch for neuron {orig_neuron['neuronID']}: " \
                f"{orig_neuron['position']} {updated_neuron['position']}"

            assert (orig_neuron["rotation"] == updated_neuron["rotation"]).all(), \
                f"Position mismatch for neuron {orig_neuron['neuronID']}: " \
                f"{orig_neuron['rotation']} {updated_neuron['rotation']}"

    def get_additional_synapses(self, synapse_distance_treshold=2.6e-6):

        # Calculate coordinate remapping for updated synapses

        voxel_size = self.updated_network_loader.data["voxelSize"]
        assert voxel_size == self.original_network_loader.data["voxelSize"], f"Voxel size mismatch between networks"

        orig_sim_origo = self.original_network_loader.data["simulationOrigo"]
        updated_sim_origo = self.updated_network_loader.data["simulationOrigo"]

        origo_diff = updated_sim_origo - orig_sim_origo
        voxel_transform = np.round(origo_diff / voxel_size)

        pre_neuron_synapses = dict()
        post_neuron_synapses = dict()

        for nid in self.updated_network_loader.get_neuron_id():
            pre_neuron_synapses[nid] = []
            post_neuron_synapses[nid] = []

        synapse_matrix = self.updated_network_loader.data["synapses"]

        keep_idx = np.zeros((synapse_matrix.shape[0],), dtype=bool)

        for idx, synapse_row in enumerate(synapse_matrix):
            pre_neuron_synapses[synapse_row[0]].append(idx)
            post_neuron_synapses[synapse_row[1]].append(idx)

        for nid in self.updated_network_loader.get_neuron_id():
            if nid % 100 == 0:
                print(f"Processing neuron {nid}")

            pre_idx = np.array(pre_neuron_synapses[nid], dtype=int)
            post_idx = np.array(post_neuron_synapses[nid], dtype=int)

            pre_coords = synapse_matrix[pre_idx, 2:5] * voxel_size + updated_sim_origo
            post_coords = synapse_matrix[post_idx, 2:5] * voxel_size + updated_sim_origo

            morph = self.get_morphology(neuron_id=nid, hdf5=self.old_hdf5,
                                        neuron_cache_id=self.old_neuron_cache_id)

            dend_kd_tree = self.get_kd_tree(morph, "dend", kd_tree_cache=self.old_kd_tree_cache)
            synapse_dend_dist, _ = dend_kd_tree.query(post_coords)
            keep_idx[post_idx[np.where(synapse_dend_dist > synapse_distance_treshold)[0]]] = True

            # Print how far away synapses were?

            if self.updated_network_loader.data["neurons"][nid]["axonDensity"] is None:
                try:
                    axon_kd_tree = self.get_kd_tree(morph, "axon", kd_tree_cache=self.old_kd_tree_cache)
                    synapse_axon_dist, _ = axon_kd_tree.query(pre_coords)
                    keep_idx[pre_idx[np.where(synapse_axon_dist > synapse_distance_treshold)[0]]] = True

                except:
                    import traceback
                    print(traceback.format_exc())
                    import pdb
                    pdb.set_trace()
            else:
                print(f"No axon for neuron {morph.name} ({nid})")

        added_synapses = synapse_matrix[keep_idx, :].copy()
        added_synapses[:, 2:5] = added_synapses[:, 2:5] + voxel_transform

        return added_synapses

    def sort_synapses(self, synapses):

        # Sort order: columns 1 (dest), 0 (src), 6 (synapse type)
        sort_idx = np.lexsort(synapses[:, [6, 0, 1]].transpose())
        return synapses[sort_idx, :].copy()

    def filter_synapses(self, filter_axon=False):

        # This replaces the original filter_synapses, so that we can also add in the
        # new synapses due to growing axons or dendrites

        # This needs to be made bigger!
        num_rows = self.old_hdf5["network/synapses"].shape[0] + self.updated_hdf5["network/synapses"].shape[0]
        num_cols = self.old_hdf5["network/synapses"].shape[1]
        new_synapses = np.zeros((num_rows, num_cols), dtype=self.old_hdf5["network/synapses"].dtype)
        syn_ctr = 0

        # Keep synapses in original network that are still within the new morphologies
        for synapses in self.synapse_iterator():
            new_syn = self.filter_synapses_helper(synapses, filter_axon=filter_axon)
            new_synapses[syn_ctr:syn_ctr + new_syn.shape[0]] = new_syn
            syn_ctr += new_syn.shape[0]

        # Here add the new synapses from growing axons and dendrites
        additional_synapses = self.get_additional_synapses()
        new_synapses[syn_ctr:syn_ctr+additional_synapses.shape[0], :] = additional_synapses
        syn_ctr += additional_synapses.shape[0]

        # Resort the new synapse matrix
        sorted_synapses = self.sort_synapses(new_synapses[:syn_ctr, :])

        self.new_hdf5["network"].create_dataset("synapses", data=sorted_synapses, compression="lzf")

        num_synapses = np.zeros((1,), dtype=np.uint64)
        self.new_hdf5["network"].create_dataset("nSynapses", data=syn_ctr, dtype=np.uint64)

        print(f"Keeping {self.new_hdf5['network/nSynapses'][()]} "
              f"out of {self.old_hdf5['network/nSynapses'][()]} synapses "
              f"({self.new_hdf5['network/nSynapses'][()] / self.old_hdf5['network/nSynapses'][()]*100:.3f} %)")

        # self.close()

    # TODO: Profile the code to see what the bottleneck is...

    # TODO: Update filter_gap_junctions to also handle growth on dendrites

    # TODO: Also handle the new inputs that might arrive on growing morphologies...