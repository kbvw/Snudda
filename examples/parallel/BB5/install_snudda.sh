#!/bin/sh

# Set up environment on BB5
module load unstable git python

# Initialize submodule of repo with mod files
git submodule update --init BasalGangliaData

# Set up Python environment
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install wheel

## Requirements taken from `pip freeze`, minus Open3D and Snudda
python -m pip install -r examples/parallel/BB5/requirements.txt

## Open3D from earlier-built wheel
python -m pip install /gpfs/bbp.cscs.ch/data/project/proj16/snudda/software/Open3D/build/lib/python_package/pip_package/open3d_cpu-0.18.0+5c982c7b5-cp311-cp311-manylinux_2_17_x86_64.whl

## Snudda as editable installation
python -m pip install -e .
