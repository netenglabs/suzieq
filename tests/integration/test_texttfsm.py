import pytest
import os
import re
import textfsm
from _pytest.mark.structures import Mark, MarkDecorator

template_dir = '/config/textfsm_templates/'
sample_dir = '/tests/integration/texttfsm/input/'


def _get_textfsm_templates():
    file_names = []
    for file in os.scandir(os.path.abspath(os.curdir) + template_dir):
        if not file.path.endswith('.tfsm'):
            continue
        t_name = re.match('(.*).tfsm', file.name).groups()[0]

        # try to get the file just to see if it exists,
        #  if not, xfail it
        try:
            _get_sample_input(t_name)
            file_names.append(t_name)
        except FileNotFoundError:
            file_names.append(pytest.param(t_name,
                                           marks=pytest.mark.xfail(reason='File Not Found',
                                                                   raises=FileNotFoundError)))
    return file_names


def _get_template(t_name):
    with open(os.path.abspath(os.curdir) + template_dir + t_name + '.tfsm', 'r') as f:
        re_table = textfsm.TextFSM(f)
    return re_table


def _get_sample_input(t_name):
    with open(os.path.abspath(os.curdir) + sample_dir + t_name + '.txt', 'r') as f:
        raw_input = f.read()

    lines = raw_input.splitlines()

    data = []
    test_input = '\n'

    for line in lines:
        data.append(line[:])

    if data:
        test_input = '\n'.join(data)
    return test_input


@pytest.mark.parametrize("template_name", _get_textfsm_templates())
def test_texttfsm(template_name):
    sample_input = _get_sample_input(template_name)
    assert sample_input
    re_table = _get_template(template_name)
    assert re_table
    parsed_out = re_table.ParseText(sample_input)
    assert parsed_out

    # records = []
    #
    # for entry in parsed_out:
    #     rentry = dict(zip(re_table.header, entry))
    #     records.append(rentry)
    #
    # print(json.dumps(records))
