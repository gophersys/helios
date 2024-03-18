#!/bin/bash

# Number of times to repeat the test
X=10

for ((i=1; i<=X; i++))
do
    echo "Test #$i"
    # Time the execution of your script using the built-in 'time' command
    (time python3 test.py) 2>&1
    echo "--------------------------------"
done
