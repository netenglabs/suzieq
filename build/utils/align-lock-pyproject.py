#!/usr/bin/env python

"""This script, given a requirements.txt file, edit the pyproject.toml
dependencies so that they match the content of the requirements file.
"""
import sys
import toml


def _usage():
    print(f'usage: {sys.argv[0]} requirements.txt pyproject.toml')
    sys.exit(0)


if __name__ == '__main__':
    args = sys.argv
    if len(args) != 3:
        _usage()

    toml_file = args[2]
    requirements_file = args[1]

    encoder = toml.encoder.TomlEncoder(preserve=True)
    dependencies = {}

    with open(requirements_file) as ifile:
        while True:
            line = ifile.readline()
            if not line:
                break
            line = line.split(';')
            version = line[0].split('==')
            dependencies[version[0]] = toml.TomlDecoder().\
                get_empty_inline_table()

            dependencies[version[0]]['version'] = version[1].strip()
            if len(line) > 1:
                dependencies[version[0]]['markers'] = line[1].strip()

    pyproject = toml.load(toml_file)

    original = pyproject['tool']['poetry']['dependencies']
    dependencies['python'] = original['python']
    pyproject['tool']['poetry']['dependencies'] = dependencies

    with open(toml_file, 'w') as pyproject_file:
        toml.dump(pyproject, pyproject_file, encoder=encoder)
