import json
import os

import h5py
import numpy as np
from scipy.spatial import KDTree

from argparse import ArgumentParser, RawTextHelpFormatter

from snudda.neurons.neuron_prototype import NeuronPrototype
from snudda.utils.load import SnuddaLoad
from snudda.utils.snudda_path import snudda_simplify_path, snudda_parse_path


class SwapToDegenerateMorphologies:

    def __init__(self, original_network_file, new_network_file,
                 original_snudda_data_dir, new_snudda_data_dir,
                 original_input_file, new_input_file):

        """ This code replaces the neuron morphologies in the original network with user provided degenerated copies
            of the neurons. The synapses that are on removed dendritic or axonal branches will also be removed.
            The section ID and section X is also updated to match the new degenerated morphologies.

            Args:
                original_network_file (str) : Path to input network-synapses.hdf5
                new_network_file (str) : Path to output network-synapses.hdf5
                original_snudda_data_dir (str) : Path to SNUDDA_DATA for original network
                new_snudda_data_dir (str) : Path to SNUDDA_DATA for new network
            """

        self.original_network_file = original_network_file
        self.new_network_file = new_network_file
        self.new_hdf5 = None

        self.original_snudda_data_dir = original_snudda_data_dir
        self.new_snudda_data_dir = new_snudda_data_dir

        self.original_input_file = original_input_file
        self.new_input_file = new_input_file

        self.original_network_loader = SnuddaLoad(self.original_network_file, load_synapses=False)
        self.old_hdf5 = self.original_network_loader.hdf5_file
        self.old_data = self.original_network_loader.data

        self.morphology_map = dict()
        self.section_lookup = dict()
        self.neuron_cache = dict()

        self.create_section_lookup()


        self.kd_tree_cache = dict()

    def write_network_new_file(self):

        print(f"Writing new network to {self.new_network_file}")
        self.new_hdf5 = h5py.File(self.new_network_file, "w")
        self.old_hdf5.copy(source=self.old_hdf5["meta"], dest=self.new_hdf5)
        network_group = self.new_hdf5.create_group("network")
        self.old_hdf5.copy(source=self.old_hdf5["network/neurons"], dest=self.new_hdf5["network"])

        # Update parameter keys and morphology keys
        for idx, neuron_id in enumerate(self.new_hdf5["network/neurons/neuronID"]):
            assert idx == neuron_id, "There should be no gaps in numbering."
            param_key, morph_key, neuron_path = self.find_morpology(neuron_id)
            self.new_hdf5[f"network/neurons/parameterKey"][idx] = param_key
            self.new_hdf5[f"network/neurons/morphologyKey"][idx] = morph_key
            self.new_hdf5[f"network/neurons/neuronPath"][idx] = neuron_path

        self.filter_synapses()
        self.filter_gap_junctions()

    def synapse_iterator(self, data_type=None, load_synapses=True):

        """ Each iteration will return the synapses between one pair of neurons. """

        data_loc = "network/synapses"
        if data_type is not None and data_type == "gapJunctions":
            data_loc = "network/gapJunctions"
            num_synapses = self.old_hdf5["network/nGapJunctions"][()][0]
        else:
            num_synapses = self.old_hdf5["network/nSynapses"][()][0]

        start_idx = 0
        next_idx = 0

        # Load synapses into memory
        if load_synapses:
            synapses = self.old_hdf5[data_loc][()].copy()
        else:
            synapses = self.old_hdf5[data_loc]

        assert num_synapses == synapses.shape[0]

        last_pre = synapses[0, 0]
        last_post = synapses[0, 1]

        while next_idx < num_synapses:
            while next_idx < num_synapses \
                    and synapses[next_idx, 0] == last_pre \
                    and synapses[next_idx, 1] == last_post:
                next_idx += 1
                if next_idx % 10000 == 0:
                    print(f"{next_idx} / {num_synapses}")

            if next_idx < num_synapses:
                last_pre = synapses[next_idx, 0]
                last_post = synapses[next_idx, 1]

            yield synapses[start_idx:next_idx, :]
            start_idx = next_idx

    def gap_junction_iterator(self, load_gap_junctions=True):

        """ Each iteration will return the gap junctions between one pair of neurons. """

        return self.synapse_iterator(data_type="gapJunctions", load_synapses=load_gap_junctions)

    def filter_synapses(self):
        # First version, will keep all synapses in memory to write a more efficient file
        new_synapses = np.zeros(self.old_hdf5["network/synapses"].shape,
                                dtype=self.old_hdf5["network/synapses"].dtype)
        syn_ctr = 0

        for synapses in self.synapse_iterator():
            new_syn = self.filter_synapses_helper(synapses)
            new_synapses[syn_ctr:syn_ctr + new_syn.shape[0]] = new_syn
            syn_ctr += new_syn.shape[0]

        self.new_hdf5["network"].create_dataset("synapses", data=new_synapses[:syn_ctr, :], compression="lzf")

        num_synapses = np.zeros((1,), dtype=np.uint64)
        self.new_hdf5["network"].create_dataset("nSynapses", data=syn_ctr, dtype=np.uint64)

    def filter_gap_junctions(self):
        # First version, will keep all synapses in memory to write a more efficient file
        new_gap_junctions = np.zeros(self.old_hdf5["network/gapJunctions"].shape,
                                     dtype=self.old_hdf5["network/gapJunctions"].dtype)
        gj_ctr = 0

        for gj in self.gap_junction_iterator():
            new_gj = self.filter_gap_junctions_helper(gj)
            new_gap_junctions[gj_ctr:gj_ctr + new_gj.shape[0]] = new_gj
            gj_ctr += new_gj.shape[0]

        self.new_hdf5["network"].create_dataset("gapJunctions", data=new_gap_junctions[gj_ctr, :], compression="lzf")

        num_gap_junctions = np.zeros((1,), dtype=np.uint64)
        self.new_hdf5["network"].create_dataset("nGapJunctions", data=gj_ctr, dtype=np.uint64)

    def get_morphology(self, neuron_id=None, hdf5=None, neuron_path=None, parameter_key=None, morphology_key=None):

        """ If neuron_id is given, that neuron will be loaded."""

        # print(f"Neuron cache size: {len(self.neuron_cache)}")

        if neuron_id is not None and neuron_id in self.neuron_cache:
            return self.neuron_cache[neuron_id]

        if (neuron_path is not None and parameter_key is not None and morphology_key is not None
                and (neuron_path, parameter_key, morphology_key) in self.neuron_cache):
            return self.neuron_cache[(neuron_path, parameter_key, morphology_key)]

        if neuron_id is not None and hdf5 is not None:
            neuron_path = SnuddaLoad.to_str(hdf5["network/neurons/neuronPath"][neuron_id])
            parameter_key = SnuddaLoad.to_str(hdf5["network/neurons/parameterKey"][neuron_id])
            morphology_key = SnuddaLoad.to_str(hdf5["network/neurons/morphologyKey"][neuron_id])

        assert neuron_path is not None and parameter_key is not None and morphology_key is not None, \
            "Either provide neuron_id, hdf5 or the three neuron_path, parameter_key and morphology_key"

        if neuron_id and hdf5:
            pos = hdf5["network/neurons/position"][neuron_id, :]
            rot = hdf5["network/neurons/rotation"][neuron_id, :].reshape(3, 3)
        else:
            pos = None
            rot = None

        neuron_prototype = NeuronPrototype(neuron_path=neuron_path, neuron_name=None)
        neuron = neuron_prototype.clone(parameter_key=parameter_key, morphology_key=morphology_key,
                                        position=pos, rotation=rot)

        if neuron_id is not None:
            self.neuron_cache[neuron_id] = neuron
        else:
            self.neuron_cache[(neuron_path, parameter_key, morphology_key)] = neuron

        return neuron

    def filter_synapses_helper(self, synapses):

        """ This currently only takes DENDRITE degeneration into account.
            AXON degeneration is not taken into account for synapse removal.
        """

        pre_id = synapses[0, 0]
        post_id = synapses[0, 1]

        assert (synapses[:, 0] == pre_id).all()
        assert (synapses[:, 1] == post_id).all()

        keep_synapses = np.ones((synapses.shape[0],), dtype=bool)

        old_sec_id = synapses[:, 9]
        old_sec_x = synapses[:, 10]

        keep_idx, new_sec_id, new_sec_x \
            = self.remap_sections_helper(neuron_id=post_id, old_sec_id=old_sec_id, old_sec_x=old_sec_x)

        edited_synapses = synapses.copy()

        edited_synapses[:, 9] = new_sec_id
        edited_synapses[:, 10] = new_sec_x

        return edited_synapses[keep_idx, :]

    def filter_gap_junctions_helper(self, gap_junctions):

        # Gap junctions are bidirectional, but call them pre and post out of habit
        pre_id = gap_junctions[0, 0]
        post_id = gap_junctions[0, 1]

        assert (gap_junctions[:, 0] == pre_id).all()
        assert (gap_junctions[:, 1] == post_id).all()

        old_pre_sec_id = gap_junctions[:, 2]
        old_pre_sec_x = gap_junctions[:, 4]
        old_post_sec_id = gap_junctions[:, 3]
        old_post_sec_x = gap_junctions[:, 5]

        keep_idx_pre, new_pre_sec_id, new_pre_sec_x \
            = self.remap_sections_helper(neuron_id=pre_id, old_sec_id=old_pre_sec_id, old_sec_x=old_pre_sec_x)

        keep_idx_post, new_post_sec_id, new_post_sec_x \
            = self.remap_sections_helper(neuron_id=post_id, old_sec_id=old_post_sec_id, old_sec_x=old_post_sec_x)

        keep_idx = np.logical_and(keep_idx_pre, keep_idx_post)

        edited_gap_junctions = gap_junctions.copy()
        edited_gap_junctions[:, 2] = new_pre_sec_id
        edited_gap_junctions[:, 3] = new_post_sec_id
        edited_gap_junctions[:, 4] = new_pre_sec_x
        edited_gap_junctions[:, 5] = new_post_sec_x

        return edited_gap_junctions[keep_idx, :]


    # TODO!! We also need to filter external input

    def find_old_morphology(self, neuron_id):

        orig_morph_key = SnuddaLoad.to_str(self.old_data["neurons"][neuron_id]["morphologyKey"])
        orig_param_key = SnuddaLoad.to_str(self.old_data["neurons"][neuron_id]["parameterKey"])
        orig_neuron_path = SnuddaLoad.to_str(self.old_data["neurons"][neuron_id]["neuronPath"])

        return orig_param_key, orig_morph_key, orig_neuron_path

    def find_morpology(self, neuron_id):

        """ Given neuron_id it looks up what was old morphology, then looks for a new morphology with the same name
            and finds the corresponding morphology_key. It also tries to pick a parameter_key """

        orig_morph_key = SnuddaLoad.to_str(self.old_data["neurons"][neuron_id]["morphologyKey"])
        orig_param_key = SnuddaLoad.to_str(self.old_data["neurons"][neuron_id]["parameterKey"])

        # We assume the new morphology is in the same relative path, but using a different SNUDDA_DATA
        orig_neuron_path = SnuddaLoad.to_str(self.old_data["neurons"][neuron_id]["neuronPath"])
        orig_simple_path = snudda_simplify_path(orig_neuron_path, self.original_snudda_data_dir)
        new_neuron_path = snudda_parse_path(orig_simple_path, self.new_snudda_data_dir)

        if orig_morph_key == '':
            # Only a single morpholoy
            return '', '', new_neuron_path

        # Here we assume there is a meta.json file
        with open(os.path.join(orig_neuron_path, "meta.json"), "r") as f:
            orig_meta_info = json.load(f)

        with open(os.path.join(new_neuron_path, "meta.json"), "r") as f:
            new_meta_info = json.load(f)

        # Find the parameter_key and morphology_key corresponding to the morphology used. Note that there might be
        # multiple parameter_key:s valid for a morphology, so then we randomly pick one of those

        orig_morph_name = orig_meta_info[orig_param_key][orig_morph_key]["morphology"]

        possible_keys = []

        for param_key, param_data in new_meta_info.items():
            for morph_key, morph_data in param_data():
                morph_name = morph_data["morphology"]
                if orig_morph_name == morph_name:
                    possible_keys.append((param_key, morph_key))

        assert len(possible_keys) > 0, \
            f"No morphology matching for {orig_morph_name}, unable to pick parameter_key and morphology_key"

        # Pick one of the key pairs
        idx = np.random.randint(low=0, high=len(possible_keys))
        new_param_key, new_morph_key = possible_keys[idx]

        return new_param_key, new_morph_key, new_neuron_path

    def get_sec_location(self, coords, neuron_path, parameter_key, morphology_key, max_dist=5e-6):

        morph = self.get_morphology(neuron_path=neuron_path,
                                    parameter_key=parameter_key,
                                    morphology_key=morphology_key)

        dend = self.get_kd_tree(morph, "dend")
        sec_id = np.zeros((dend.shape[0],), dtype=int)
        sec_x = np.zeros((dend.shape[0],))

        coord_to_sec_id_x = dict()
        for link, sec_id, sec_x in zip(morph.dend_links, morph.dend_sec_id, morph.dend_sec_x):
            coord = morph.dend[link[1], :]

            coord_to_sec_id_x[coord] = (sec_id, sec_x[1])

        for idx, coord in enumerate(coords):
            closest_dist, closest_point = dend.query(coord)

            if closest_dist < max_dist:
                syn_sec_id, syn_sec_x = coord_to_sec_id_x[morph.dend[closest_point, :3]]
                sec_id[idx] = syn_sec_id
                sec_x[idx] = syn_sec_x
            else:
                sec_id[idx] = np.nan
                sec_x[idx] = np.nan

        return sec_id, sec_x

    def write_new_input_file(self):

        print(f"Writing new input data to {self.new_input_file}")

        old_input = h5py.File(self.original_input_file, "r")
        new_input = h5py.File(self.new_input_file, "w")
        old_input.copy(source=old_input["config"], dest=new_input)

        new_input.create_group("input")

        for neuron in old_input["input"].keys():
            neuron_group = new_input["input"].create_group(neuron)

            for input_type in old_input["input"][neuron].keys():
                # Note: This code assumes these are real neuron and not just virtual neurons.
                #       it does not handle the virtual neuron case here.
                old_input_data = old_input["input"][neuron][input_type]

                keep_idx, new_sec_id, new_sec_x \
                    = self.remap_sections_helper(neuron_id=int(neuron),
                                                 old_sec_id=old_input_data["sectionID"],
                                                 old_sec_x=old_input_data["sectionX"])

                if len(keep_idx) == 0:
                    continue

                input_group = neuron_group.create_group(input_type)

                input_group.create_dataset("spikes", data=old_input_data[:, keep_idx], compression="gzip",
                                           dtype=np.float32)
                input_group.create_dataset("nSpikes", data=old_input_data["nSpikes"][keep_idx], dtype=np.int32)
                input_group.create_dataset("sectionID", data=new_sec_id,
                                           compression="gzip", dtype=np.int16)
                input_group.create_dataset("sectionX", data=new_sec_x,
                                           compression="gzip", dtype=np.float16)

                input_group.create_dataset("distanceToSoma", data=old_input_data["distanceToSoma"][keep_idx],
                                           compression="gzip", dtype=np.float16)

                for data_name in ["freq", "correlation", "jitter", "synapseDensity", "start", "end", "conductance",
                                  "populationUnitID", "populationUnitSpikes", "generator",
                                  "modFile", "parameterFile", "parameterList", "parameterID"]:
                    if data_name in old_input_data:
                        old_input_data.copy(source=old_input_data[data_name], dest=input_group)

        old_input.close()
        new_input.close()

    def get_kd_tree(self, neuron, tree_type):

        if (neuron, tree_type) not in self.kd_tree_cache:

            coords = {"axon": neuron.axon[:, :3],
                      "dend": neuron.dend[:, :3]}

            if coords[tree_type].size > 0:
                self.kd_tree_cache[(neuron, tree_type)] = KDTree(coords[tree_type])
            else:
                self.kd_tree_cache[(neuron, tree_type)] = None

        return self.kd_tree_cache[(neuron, tree_type)]

    def create_section_lookup(self):

        for neuron_id in self.old_hdf5["network/neurons/neuronID"]:
            self.create_section_lookup_helper(neuron_id)

    # Note this does not take AXON degeneration into account, need to do that separately
    def create_section_lookup_helper(self, neuron_id):

        old_param_key, old_morph_key, old_path = self.find_old_morphology(neuron_id=neuron_id)
        new_param_key, new_morph_key, new_path = self.find_morpology(neuron_id=neuron_id)

        if (old_param_key, old_morph_key, old_path) in self.section_lookup:
            # We already have the morphology in the section_lookup
            return

        old_morph = self.get_morphology(parameter_key=old_param_key,
                                        morphology_key=old_morph_key,
                                        neuron_path=old_path)

        new_morph = self.get_morphology(parameter_key=new_param_key,
                                        morphology_key=new_morph_key,
                                        neuron_path=new_path)

        coord_to_sec_id_x = dict()
        for link, old_sec_id, old_sec_x in zip(old_morph.dend_links, old_morph.dend_sec_id, old_morph.dend_sec_x):
            coord = (old_morph.dend[link[1], :3] * 1e3).astype(int)
            coord_to_sec_id_x[coord[0], coord[1], coord[2]] = (old_sec_id, old_sec_x[1])

        old_to_new_sec_id = dict()
        old_sec_x_list = dict()  # We just need to find the maximal old sec_x still present,
                                 # that value will map to sec_x 1.0 in new (stored as int sec_x*1000)

        for link, new_sec_id, new_sec_x in zip(new_morph.dend_links, new_morph.dend_sec_id, new_morph.dend_sec_x):
            coord = (new_morph.dend[link[1], :3] * 1e3).astype(int)
            old_sec_id, old_sec_x = coord_to_sec_id_x[coord[0], coord[1], coord[2]]

            old_to_new_sec_id[old_sec_id] = new_sec_id
            if old_sec_id not in old_sec_x_list:
                old_sec_x_list[old_sec_id] = [old_sec_x]
            else:
                old_sec_x_list[old_sec_id].append(old_sec_x)

        neuron_section_lookup = dict()
        for old_sec_id in old_to_new_sec_id.keys():
            neuron_section_lookup[old_sec_id] = (old_to_new_sec_id[old_sec_id], np.max(old_sec_x_list[old_sec_id]))

        self.section_lookup[old_param_key, old_morph_key, old_path] = neuron_section_lookup

    def remap_sections_helper(self, neuron_id, old_sec_id, old_sec_x):

        """
            Remaps sections for neuron_id

            This does currently NOT take AXON DEGENERATION into account

            Args:
                neuron_id (int) : Neuron ID
                old_sec_id (np.array) : Section ID of old section
                old_sec_x (np.array) : Section X of old section (note in synapse matrix format, int 0-1000)

            Returns:
                keep_idx (np.array) : Bool array
                new_sec_id (np.array) : Section ID of new section, positions are np.nan if not mapped
                new_sec_x (np.array) : Section X of new section, positions are np.nan if not mapped

        """

        keep_idx = np.zeros(old_sec_id.shape, dtype=bool)
        new_sec_id = np.zeros(old_sec_id.shape, dtype=int) * np.nan
        new_sec_x = np.zeros(old_sec_id.shape, dtype=int) * np.nan

        old_param_key, old_morph_key, old_path = self.find_old_morphology(neuron_id=neuron_id)

        lookup = self.section_lookup[old_param_key, old_morph_key, old_path]

        for idx, (old_id, old_x) in enumerate(zip(old_sec_id, old_sec_x)):
            if old_id in lookup and old_x <= lookup[old_id][1]:
                new_id = lookup[old_id][0]
                new_x = old_x / lookup[old_id][1] * 1000

                keep_idx[idx] = True
                new_sec_id[idx] = new_id
                new_sec_x[idx] = new_x

        return keep_idx, new_sec_id, new_sec_x


def cli():
    parser = ArgumentParser(
        description="Replace WT morphologies with PD morphologies, remove orphaned synapses and input",
        formatter_class=RawTextHelpFormatter)

    parser.add_argument("original_network_path", type=str)
    parser.add_argument("new_network_path", type=str)
    parser.add_argument("original_snudda_path", type=str)
    parser.add_argument("new_snudda_path", type=str)

    args = parser.parse_args()

    if not os.path.isdir(args.new_network_path):
        os.mkdir(args.new_network_path)

    original_network_file = os.path.join(args.original_network_path, "network-synapses.hdf5")
    new_network_file = os.path.join(args.new_network_path, "network-synapses.hdf5")
    original_input_file = os.path.join(args.original_network_path, "input-spikes.hdf5")
    new_input_file = os.path.join(args.new_network_path, "input-spikes.hdf5")

    swap = SwapToDegenerateMorphologies(original_network_file=original_network_file,
                                        new_network_file=new_network_file,
                                        original_snudda_data_dir=args.original_snudda_path,
                                        new_snudda_data_dir=args.new_snudda_path,
                                        original_input_file=original_input_file,
                                        new_input_file=new_input_file)
    swap.write_network_new_file()
    swap.write_new_input_file()


if __name__ == "__main__":
    cli()
