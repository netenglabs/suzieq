import pytest
import os
import re
import textfsm
import yaml

template_dir = '/config/textfsm_templates/'
input_dir = '/tests/integration/texttfsm/input/'
processed_dir = '/tests/integration/texttfsm/processed/'


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
    with open(os.path.abspath(os.curdir) + input_dir + t_name + '.txt', 'r') as f:
        raw_input = f.read()

    lines = raw_input.splitlines()

    data = []
    test_input = '\n'

    for line in lines:
        data.append(line[:])

    if data:
        test_input = '\n'.join(data)
    return test_input


def _get_processed_data(template_name):
    d = os.path.abspath(os.curdir) + processed_dir
    file_name = f"{d}/{template_name}.yml"
    with open(file_name, 'r') as f:
        out = yaml.load(f.read())
    return out


@pytest.mark.parametrize("template_name", _get_textfsm_templates())
def test_texttfsm(template_name, tmp_path):
    sample_input = _get_sample_input(template_name)
    assert sample_input
    re_table = _get_template(template_name)
    assert re_table
    created_records = re_table.ParseText(sample_input)
    assert created_records

    # this is the code necessary to write out the data
    # file = tmp_path / f"{template_name}.yml"
    # print(f"writing to {file}")
    # file.write_text(yaml.dump(created_records))

    processed_records = _get_processed_data(template_name)
    assert processed_records == created_records

