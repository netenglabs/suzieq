#!/usr/bin/python3

import sys
import json

import textfsm
# Read the tfsm file from args
with open(sys.argv[1], 'r') as f:
    raw_input = f.read()

# Suck out the comment lines, all at the start and supply as input
lines = raw_input.splitlines()

data = []
test_input = '\n'

for line in lines:
    if line.startswith('#'):
        data.append(line[1:])

if data:
    test_input = '\n'.join(data)

with open(sys.argv[1], 'r') as f:
    re_table = textfsm.TextFSM(f)

parsed_out = re_table.ParseText(test_input)

records = []

for entry in parsed_out:
    rentry = dict(zip(re_table.header, entry))
    records.append(rentry)

print(json.dumps(records))
