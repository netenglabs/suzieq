Contributing code to Suzieq typically requires programming in python (specifically python 3). The recommended best practice for programming in python requires the use of [virtual environments](https://realpython.com/python-virtual-environments-a-primer/). Suzieq relies on a number of other open source projects to do its job. Installing those packages and the right versions is also crucial before starting to develop for Suzieq. 

We use [poetry](https://python-poetry.org/) to both setup the working virtual environment for Suzieq and to install the appropriate packages. Therefore, before you can get started in developing for Suzieq, you must get a working development environment. __I have developed only in Linux, but I know of others who've developed on macOS. I cannot vouch for the development on Windows because several packages work only on Linux or macOS__.

Setting up the development environment for Suzieq involves the following steps:

* Make sure you have a python3 version that is > 3.7.1 and less than 3.9.0. If you don't have a system provided python version that matches this requirement, you can use [pyenv](https://realpython.com/intro-to-pyenv/) to install one.
* If you've used pyenv to install a specific python version, ensure you activate it.
* Install poetry--follow the instructions posted [here](https://python-poetry.org/docs/#installation).
* Install *poetry-dynamic-versioning* -- follow the instructions posted
  [here](https://pypi.org/project/poetry-dynamic-versioning/)
* Ensure you have git installed (follow the instructions [here](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git))
* Clone the github repository: ```git clone https://github.com/netenglabs/suzieq.git```. This creates a copy of the code repository in the subfolder suzieq in the current directory. 
* Create the virtual environment and install the appropriate packages by typing: ```poetry install```
* Activate the virtual environment by typing ```poetry shell```

Now you're ready to get started writing code for Suzieq.
