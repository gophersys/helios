#!/bin/bash

# Check if exactly one argument is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <number_of_times>"
    exit 1
fi

# Assign the argument to a variable
NUMBER_OF_TIMES=$1

# Ensure the argument is an integer
if ! [[ $NUMBER_OF_TIMES =~ ^[0-9]+$ ]]; then
    echo "Error: <number_of_times> must be an integer."
    exit 1
fi

# Loop to run the command the specified number of times
for (( i=1; i<=NUMBER_OF_TIMES; i++ ))
do
    echo "Running iteration $i"
    python3 test/client.py read-altimeter
done

echo "Completed running the command $NUMBER_OF_TIMES times."