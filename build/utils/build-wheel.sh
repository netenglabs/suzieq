#!/bin/bash
# At the moment poetry does not allow to build a wheel fixing the dependency
# to the value of the poetry.lock.
# As reported in this open issue:
# https://github.com/python-poetry/poetry/issues/2778
# This causes some unexpected behaviour as the wheel installs libraries that
# has not been tested.
# This script allows to build a wheel with the dependencies pinned in the lock
# file
abort(){
    printf "\033[0;31m$1\n\033[0m"
    echo SuzieQ wheel build aborted...
    exit -1
}

REQUIREMENTS="/tmp/suzieq-requirements.txt"

# We need to check that there are not changes in the pyproject.toml
git diff --quiet pyproject.toml
if [ $? -ne 0 ]
then
    abort "There are changes in your pyproject.toml, commit them before proceeding with the build."
fi

# Create the requirements.txt file
echo -e "\U0001F4D6 Creating the requirements.txt file with the dependencies..."
poetry export -f requirements.txt --without-hashes > $REQUIREMENTS
if [ $? -ne 0 ]
then
    abort "Unable to create requirements.txt file."
fi

if [ $? -ne 0 ]
then
    abort "I need to execute in the poetry shell environment."
fi

echo -e "\U0001F4CC Fixing the dependencies..."
$(dirname $0)/align-lock-pyproject.py $REQUIREMENTS pyproject.toml
if [ $? -ne 0 ]
then
    abort "Unable fix dependencies in pyproject.toml."
fi

echo -e "\U0001F528 Building the SuzieQ package..."
poetry build
if [ $? -ne 0 ]
then
    abort "Poetry build failed."
fi

echo -e "\U0001F519 Restoring the pyproject.toml file"
git restore pyproject.toml

echo -e "\U0002705 Suzieq Build completed"
