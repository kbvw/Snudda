import os.path

import h5py
import numpy as np
from mpi4py import MPI  # This must be imported before neuron, to run parallel
from neuron import h  # , gui


class SnuddaSaveNetworkActivity:

    def __init__(self, output_file, network_data=None):

        self.output_file = output_file
        self.network_data = network_data

        self.pc = h.ParallelContext()

    def spike_sort(self, t_spikes, id_spikes):

        spike_count = dict()

        for t, idx in zip(t_spikes, id_spikes):
            if idx in spike_count:
                spike_count[idx] += 1
            else:
                spike_count[idx] = 1

        spikes = dict()
        spike_ctr = dict()

        for idx, num in spike_count.items():
            spikes[idx] = np.full((num,), np.nan)  # Initialise to NaN to catch any unassigned values
            spike_ctr[idx] = 0

        for t, idx in zip(t_spikes, id_spikes):
            spikes[idx][spike_ctr[idx]] = t
            spike_ctr[idx] += 1

        for nid in self.network_data["neuronID"]:
            if nid not in spikes:
                spikes[nid] = np.zeros((0, ))

        # Internal consistency
        for idx in spikes:
            assert len(spikes[idx]) == 0 or not np.isnan(spikes[idx][-1])
            assert (idx in spike_ctr and spikes[idx].shape[0] == spike_ctr[idx]) \
                or (idx not in spike_ctr and len(spikes[idx]) == 0)

        return spikes

    def write(self, t_save, v_save, v_key, t_spikes, id_spikes, output_file=None):

        if not output_file:
            output_file = self.output_file

        self.pc.barrier()

        if int(self.pc.id()) == 0:

            if not os.path.isdir(os.path.dirname(output_file)):
                os.mkdir(os.path.dirname(output_file))

            print(f"Writing network output to {output_file}")
            out_file = h5py.File(output_file, "w")

            meta_data = out_file.create_group("metaData")
            out_file.create_group("voltData")
            out_file.create_group("spikeData")

            if self.network_data:
                neuron_id = np.array([x["neuronID"] for x in self.network_data["neurons"]])
                meta_data.create_dataset("ID", data=neuron_id)

                neuron_names = [x["name"] for x in self.network_data["neurons"]]
                str_type = 'S' + str(max(1, max([len(x) for x in neuron_names])))
                meta_data.create_dataset("name", (len(neuron_names),), str_type, neuron_names, compression="gzip")

                neuron_types = [x["type"] for x in self.network_data["neurons"]]
                str_type = 'S' + str(max(1, max([len(x) for x in neuron_types])))
                meta_data.create_dataset("type", (len(neuron_names),), str_type, neuron_names, compression="gzip")

                swc_list = [n["morphology"] for n in self.network_data["neurons"]]
                max_swc_len = max([len(x) for x in swc_list])
                meta_data.create_dataset("morphology", (len(swc_list),), f"S{max_swc_len}",
                                         swc_list, compression="gzip")

                parameter_keys = [n["parameterKey"] for n in self.network_data["neurons"]]
                parameter_key_length = max([len(x) for x in parameter_keys])
                meta_data.create_dataset("parameterKey", (len(parameter_keys),), f"S{parameter_key_length}",
                                         parameter_keys, compression="gzip")

                morphology_keys = [n["morphologyKey"] for n in self.network_data["neurons"]]
                morphology_key_length = max(1, max([len(x) for x in morphology_keys]))
                meta_data.create_dataset("morphologyKey", (len(morphology_keys),), f"S{morphology_key_length}",
                                         morphology_keys, compression="gzip")

                modulation_keys = [n["modulationKey"] for n in self.network_data["neurons"]]
                modulation_key_length = max(1, max([len(x) for x in modulation_keys]))
                meta_data.create_dataset("modulationKey", (len(modulation_keys),), f"S{modulation_key_length}",
                                         modulation_keys, compression="gzip")

                meta_data.create_dataset("populationUnit", data=self.network_data["populationUnit"], compression="gzip")
                meta_data.create_dataset("position", data=self.network_data["neuronPositions"], compression="gzip")

            out_file.close()

        if not t_save or not v_save or not v_key:
            print("No voltage data saved.")
        else:
            print("Saving voltage data...")
            for i in range(int(self.pc.nhost())):

                if i == int(self.pc.id()):
                    out_file = h5py.File(output_file, "a")

                    if i == 0:
                        out_file["voltData"].create_dataset("time", data=t_save * 1e-3, compression="gzip")

                    for neuron_id, voltage in zip(v_key, v_save):
                        out_file["voltData"].create_dataset(str(neuron_id), data=voltage*1e-3, compression="gzip")

                    out_file.close()

                self.pc.barrier()

        # Write spike data
        print("Sorting spikes")
        spikes = self.spike_sort(t_spikes=t_spikes, id_spikes=id_spikes)

        print("Saving spike data...")

        for i in range(int(self.pc.nhost())):
            if i == int(self.pc.id()):
                out_file = h5py.File(output_file, "a")

                for idx, spike_times in spikes.items():
                    out_file["spikeData"].create_dataset(f"{idx:.0f}", data=spike_times*1e-3, compression="gzip")

                out_file.close()

            self.pc.barrier()
