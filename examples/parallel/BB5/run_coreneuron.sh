#!/bin/bash -l
#SBATCH --account=proj16 
#SBATCH --partition=prod
#SBATCH --time=08:00:00
#SBATCH --nodes=4 
#SBATCH --exclusive 
#SBATCH --mem=0
#SBATCH --constraint=uc3
#SBATCH --output=log/snudda_coreneuron.log
#SBATCH --error=log/snudda_coreneuron.error.log

# Set up environment on BB5
module load unstable python
. .venv/bin/activate

## Module NEURON
module load neuron

## Virtual environment at the end of PYTHONPATH, only for Snudda dependencies
export PYTHONPATH=$PYTHONPATH:$PWD/.venv/lib/python3.11/site-packages:$PWD

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
srun $JOBDIR/x86_64/special -mpi -python $SNUDDA_DIR/simulate/simulate.py $JOBDIR/network-synapses.hdf5 $JOBDIR/input-spikes.hdf5 -coreneuron --time 3.5
