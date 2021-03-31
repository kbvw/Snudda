#!/bin/bash

# Download and install miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod u+x Miniconda3-latest-Linux-x86_64.sh

module load snic-env
L=/cfs/klemming/nobackup/${USER:0:1}/$USER/local/$SNIC_RESOURCE

./Miniconda3-latest-Linux-x86_64.sh -b -p $L/miniconda3

source activate_miniconda.txt
conda activate

# This is needed to compile mpi4py
if [ $SNIC_RESOURCE == "tegner" ]; then
    module load gcc/9.2.0
    module load openmpi/4.1-gcc-9.2
elif [ $SNIC_RESOURCE == "beskow" ]; then
    module load gcc/10.1.0
    module load ??? # What is openmpi module on Beskow?
   #do something
fi

# Install Snudda
pushd $L
git clone git@github.com:Hjorthmedh/Snudda.git
cd Snudda
pip install -r requirements.txt

popd

