#!/bin/bash

# nohup ./run.sh 2>&1 > temp/run.log &

# parameter
CC_MODES=("AoR")
TX_NUM=1000
CHAIN_NUMS=($(seq 170 10 200)) 
XTXRATIOS=($(seq 0.8 0.2 0.8))


# Create log directory
mkdir -p temp/logs

# Iterate through all parameter combinations
for xtxratio in "${XTXRATIOS[@]}"; do
    for ccmode in "${CC_MODES[@]}"; do
        for chainnum in "${CHAIN_NUMS[@]}"; do
            # Build log file name (contains parameter information)
            log_file="temp/logs/evaluate_${ccmode}_${TX_NUM}_${chainnum}_${xtxratio}.log"
            
            echo "config: CCMode=$ccmode, TxNum=$TX_NUM, ChainNum=$chainnum, XTXRatio=$xtxratio"
            
            # Execute command
            nohup python locals_unix/evaluate.py \
                --ccmode="$ccmode" \
                --txnum=$TX_NUM \
                --xtxratio=$xtxratio \
                --chainnum=$chainnum \
                2>&1 > "$log_file" &
                
            # Wait for the current nohup process to complete
            wait $!
        done
    done
done

echo "All tasks have been started"
