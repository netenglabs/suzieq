#!/usr/bin/env python3

import sys
import yaml
import json
import argparse
import os

from suzieq.service import cons_recs_from_json_template


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--sample-dir', '-I', type=str,
                        default='./tests/samples/',
                        help='Directory where sample outputs are stored')
    parser.add_argument('--service', '-s', type=str, required=True,
                        help='Name of service to test')
    parser.add_argument('--service-dir', '-S', type=str, default='./config',
                        help='Directory where service file definition is stored')
    parser.add_argument('--device-type', '-d', type=str,
                        help='Device type to test', default='cumulus')

    userargs = parser.parse_args()

    if not os.path.exists(userargs.sample_dir):
        print('Directory with sample outputs {} not present'.format(
            userargs.sample_dir))
        sys.exit(1)

    if not os.path.exists('{}/{}.yml'.format(userargs.sample_dir, userargs.service)):
        print('No sample output found for service {} in {}'.format(
            userargs.service, userargs.sample_dir))
        sys.exit(1)

    if not os.path.exists(userargs.service_dir):
        print('Directory with service definitions {} not present'.format(
            userargs.service_dir))
        sys.exit(1)

    if not os.path.exists('{}/{}.yml'.format(userargs.service_dir, userargs.service)):
        print('No service definition found for service {} in {}'.format(
            userargs.service, userargs.service_dir))
        sys.exit(1)

    with open('{}/{}.yml'.format(userargs.service_dir, userargs.service), 'r') as f:
        svcdef = yaml.load(f.read())

    with open('{}/{}.yml'.format(userargs.sample_dir, userargs.service), 'r') as f:
        yml_inp = yaml.load(f.read())

    # Extract the appropriate svc definition

    svcstr = svcdef.get('apply', {}) \
                   .get(userargs.device_type, {}) \
                   .get('normalize', '')

    if not svcstr:
        print('No normalization service string found for {} in {}/{}'.format(
            userargs.device_type, userargs.service_dir, userargs.service))
        sys.exit(1)

    raw_input = yml_inp.get('input', {}) \
                       .get(userargs.device_type, '')

    if not raw_input:
        print('No normalization service string found for {} in {}/{}'.format(
            userargs.device_type, userargs.sample_dir, userargs.service))
        sys.exit(1)

    records = cons_recs_from_json_template(svcstr, json.loads(raw_input))

    print(json.dumps(records))
