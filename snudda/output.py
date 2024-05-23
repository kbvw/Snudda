import h5py # type: ignore

from typing import Optional, Iterable, Iterator

def spikes_to_text(
   h5_file: str,
   text_file: str,
   time_range: Optional[tuple[float, float]] = None,
   neurons: Optional[Iterable[str]] = None,
):

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
