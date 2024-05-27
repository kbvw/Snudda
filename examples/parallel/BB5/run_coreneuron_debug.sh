#!/bin/bash -l
#SBATCH --account=proj16 
#SBATCH --partition=prod
#SBATCH --time=08:00:00
#SBATCH --nodes=4 
#SBATCH --exclusive 
#SBATCH --mem=0
#SBATCH --constraint=uc3
#SBATCH --output=log/snudda_coreneuron_debug.log
#SBATCH --error=log/snudda_coreneuron_debug.error.log

# Set up environment on BB5
module load unstable git gcc hpe-mpi python
. .venv/bin/activate

## Neuron built with zero optimizations
export PATH=/gpfs/bbp.cscs.ch/data/project/proj16/snudda/software/nrn/build/bin:$PATH
export PYTHONPATH=/gpfs/bbp.cscs.ch/data/project/proj16/snudda/software/nrn/build/lib/python:$PYTHONPATH

# Environment variables read by Snudda
export SNUDDA_DIR=$PWD/snudda
export SNUDDA_DATA=$PWD/BasalGangliaData/data

# Directory as created in `create_network` script
JOBDIR=$PWD/test_100

# Compile mod files
cd $JOBDIR
if [ -d x86_64 ]; then
  rm x86_64 -rf
fi
nrnivmodl -coreneuron $SNUDDA_DATA/neurons/mechanisms
cd ..

# Run simulation
srun -n 4 $JOBDIR/x86_64/special -mpi -python $SNUDDA_DIR/simulate/simulate.py $JOBDIR/network-synapses.hdf5 $JOBDIR/input-spikes.hdf5 -coreneuron --time 3.5
