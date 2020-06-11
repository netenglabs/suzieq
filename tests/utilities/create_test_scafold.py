# usually used for test_sqs
# creates a new test output file

import yaml
import argparse

basic_verbs = ['show', 'summarize', 'unique']

# a list of [cmd, [list of verbs for the command], [list of for each verb filters]]
command_table = [
    ['address', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']],
    ['arpnd', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']],
    ['bgp', basic_verbs + ['assert'],
     [[None, '--columns=hostname'],
      None,
      [None, '--columns=hostname'],
      None]],
    ['device', basic_verbs,
     [[None, '--columns=hostname'],
      [None,
       '--columns="namespace hostname"'],
      ['--columns=hostname',
       '--columns="hostname namespace"',
       '--columns=badcolumn']]],
    ['evpnVni', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']],
    ['interface', basic_verbs + ['assert', 'top'],
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname', None, None, None]],
    ['lldp', basic_verbs,
     [[None, '--columns=hostname'],
      [None, ],
      '--columns=hostname']],
    ['mac', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']],
    ['mlag', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']],
    ['ospf', basic_verbs + ['assert', 'top'],
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname',
      None,
      None]],
    ['path', ['show', 'summarize'],
     [[None,
       '--dest=172.16.2.104 --src=172.16.1.101',
       '--dest=172.16.2.104 --src=172.16.1.104',
       '--dest=10.0.0.11 --src=10.0.0.14',
       '--src=172.16.1.101 --dest=172.16.253.1'],
      ['--dest=172.16.2.104 --src=172.16.1.101',
       '--dest=10.0.0.11 --src=10.0.0.14']]],
    ['sqpoller', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']],
    ['route', basic_verbs + ['lpm'],
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname',
      ['--address=10.0.0.1',
       '--address="10.0.0.12"',
       '--address="10.0.0.12" --hostname="server101 server103"',
       '--address="10.0.0.12" --vrf=evpn-vrf', # TODO: have to do something about suplying vpn
       '--address="10.0.0.11" --vrf=evpn-vrf',
       ]]],
    ['table', ['show', 'describe'],
     [[None, '--columns=hostname', '--namespace=dummy',
       '--view=changes',
       '--view=latest',
       '--hostname=leaf01'],
      [None],
      '--columns=hostname',
      '--table=system']],
#    ['topcpu', basic_verbs,
#     [[None, '--columns=hostname'],
#      [None],
#      '--columns=hostname']],
#    ['topmem', basic_verbs,
#     [[None, '--columns=hostname'],
#      [None],
#      '--columns=hostname']],
    ['vlan', basic_verbs,
     [[None, '--columns=hostname'],
      [None],
      '--columns=hostname']]
]


def test_command(cmd, verbs, filters, data_directory, yaml_directory):
    output = {}
    output['description'] = f"Testing verbs for {cmd}: {' '.join(verbs)}"
    output['tests'] = []
    for verb, filt in zip(verbs, filters):
        if filt and isinstance(filt, list):
            for fi in filt:
                output['tests'].append(_create_specific_test(cmd, verb, fi,
                                                             data_directory))
        else:
            output['tests'].append(_create_specific_test(cmd, verb, filt,
                                                         data_directory))

    filename = f"{yaml_directory}/{cmd}.yml"

    with open(filename, 'w') as f:
        f.write(yaml.dump(output))


def _create_specific_test(cmd, verb, filter=None, data_directory=None):
    if data_directory:
        test = {'data-directory': data_directory, 'marks': f"{cmd} {verb}"}
    else:
        test = {'marks': f"{cmd} {verb}"}
    if filter:
        test['command'] = f"{cmd} {verb} {filter} --format=json"
    else:
        test['command'] = f"{cmd} {verb} --format=json"

    return test


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('--directory', '-d', type=str)
    parser.add_argument('--data', '-D', type=str, help='data directory')
    userargs = parser.parse_args()
    for cmd in command_table:
        test_command(cmd[0], cmd[1], cmd[2], userargs.data, userargs.directory)
