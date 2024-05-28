#!/bin/sh

# Network size: Dardel example uses 10k, using 100 here for a small test
JOBDIR=$PWD/test_10000
SIMSIZE=10000

# Environment variables read by Snudda
export SNUDDA_DIR=$PWD/snudda
export SNUDDA_DATA=$PWD/BasalGangliaData/data

# Activate virtual environment
. .venv/bin/activate

# Create network with parameters same parameters as Dardel example
mkdir -p $JOBDIR
snudda init ${JOBDIR} --size ${SIMSIZE} --overwrite --randomseed 1234
snudda place ${JOBDIR}
snudda detect ${JOBDIR} --hvsize 50
snudda prune ${JOBDIR}
cp -a $SNUDDA_DIR/data/input_config/input-v10-scaled.json ${JOBDIR}/input.json
snudda input ${JOBDIR} --time 5
