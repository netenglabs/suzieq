# this takes a sqcmds output yaml file
#  and produces the right output for it.
import sys
import yaml
import json
import shlex
import argparse
from subprocess import check_output, CalledProcessError
from tests import conftest


def create_config(testvar):
    if 'data-directory' in testvar:
        # We need to create a tempfile to hold the config
        tmpconfig = conftest._create_context_config()
        tmpconfig['data-directory'] = testvar['data-directory']

        tmpfname = '/tmp/test-sq.cfg'
        with open(tmpfname, 'w') as f:
            f.write(yaml.dump(tmpconfig))
        return tmpfname


def run_cmd(cmd_path, testvar, namespace=None):
    exec_cmd = cmd_path + shlex.split(testvar['command'])
    if namespace:
        exec_cmd += ['--namespace', namespace]
    output = None
    error = None
    cmds = exec_cmd[:]
    _ = cmds.pop(0)
    _ = cmds.pop(0)
    print(f"running {cmds}")
    try:
        output = check_output(exec_cmd)
    except CalledProcessError as e:
        error = e.output
        print(f"ERROR: {e.output} {e.returncode}")

    jout = []
    jerror = []
    xfail = False
    if output:
        try:
            jout = json.loads(output.decode('utf-8').strip())
        except json.JSONDecodeError:
            jout = output.decode('utf-8').strip()
    if error:
        try:
            jerror = json.loads(error.decode('utf-8').strip())
        except json.JSONDecodeError:
            # most likely this was an uncaught exception, so it's formatting is
            #  not sufficient for json
            jerror = error.decode('utf-8').strip()
            xfail = True
    return jout, jerror, xfail


if __name__ == '__main__':

    sqcmd_path = [sys.executable, conftest.suzieq_cli_path]
    parser = argparse.ArgumentParser()

    parser.add_argument('--filename', '-f', type=str, required=True)
    parser.add_argument('--data_dir', '-d', type=str)
    parser.add_argument('--overwrite', '-o', action='store_true')
    parser.add_argument('--namespace', '-n', type=str)
    userargs = parser.parse_args()

    with open(userargs.filename, 'r') as f:
        data = yaml.load(f.read(), Loader=yaml.BaseLoader)

    changes = 0
    for test in data['tests']:
        result = None
        if 'error' in test:
            result = 'error'
        elif 'xfail' in test:
            result = 'xfail'
        elif 'output' in test:
            result = 'output'

        if result not in test or test[result] is None or userargs.overwrite:
            changes += 1
            if userargs.data_dir:
                test['data-directory'] = userargs.data_dir

            cfg_file = create_config(test)
            sqcmd = sqcmd_path + ['--config={}'.format(cfg_file)]

            reason = None
            output, error, xfail = run_cmd(sqcmd, test, userargs.namespace)

            # make sure that the result is the same class of result from before
            # there would be no result if no output had been specified in the captured output
            # sometimes we correctly produce no results, so avoid checking that
            if result and (output or error or xfail):
                assert globals()[result], \
                    f"result {result}, output: {output}, error: {error}, xfail: {xfail}"

            # TODO: what to do when captured output is correctly empty []

            if not error and result != 'xfail':
                if result in test:
                    del test[result]
                result = 'output'
                test[result] = json.dumps(output)
            elif result == 'xfail':
                test[result]['error'] = json.dumps(output)
            else:
                result = 'error'
                if xfail:
                    result = 'xfail'
                    reason = 'uncaught exception'
                if result not in test:
                    test[result] = {}
                test[result]['error'] = json.dumps(error)
                if reason:
                    test[result]['reason'] = reason
                if 'output' in test:
                    del test['output']
    if changes:
        with open(userargs.filename, 'w') as f:
            yaml.dump(data, f)
