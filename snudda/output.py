import h5py # type: ignore

from typing import Optional, Iterable, Iterator

def spikes_to_text(
   h5_file: str,
   text_file: str,
   time_range: Optional[tuple[float, float]] = None,
   neurons: Optional[Iterable[str]] = None,
):
    """Write spikes from Snudda HDF5 output to plain text.

    Parameters
    ----------
    h5_file : str
        Name of input HDF5 file to read the spikes from.
    text_file : str
        Name of text file to write the spikes to.
    time_range : tuple[float, float], optional
        A time range (start, stop): if passed, only spikes at
        start <= t < stop will be written to the output.
    neurons : Iterable[str], optional
        An iterable of neuron IDs: if passed, only spikes from
        neurons in the iterable will be written to the output.
    """

    with (
        h5py.File(h5_file) as in_data,
        open(text_file, 'w') as out_data,
    ):

        spikes: Iterator[tuple[str, Iterable[float]]]
        spikes = ((id, list(nrn_data['spikes'][0])) for id, nrn_data in in_data['neurons'].items())

        if neurons is not None:
            spikes = filter(lambda s: s[0] in set(neurons), spikes)

        if time_range is not None:
            start, end = time_range
            spikes = ((id, filter(lambda s: start <= s < end, spike_list))
                      for id, spike_list in spikes)

        for id, spike_list in spikes:
            for s in spike_list:
                out_data.write(str(id) + '\t' + str(s) + '\n')
