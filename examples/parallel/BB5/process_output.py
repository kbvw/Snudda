if __name__ == '__main__':

    # Directory as created in `create_network` script
    JOBDIR = 'test_100'

    from snudda.output import spikes_to_text
    spikes_to_text(JOBDIR + '/simulation/output.hdf5', 'spikes.txt')
