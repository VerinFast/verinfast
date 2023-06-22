#! /bin/bash

# Debugging script to clear data and rerun
rm resultslog.txt
rm -rf results temp_repo
./agent.py
