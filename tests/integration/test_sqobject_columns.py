from typing import Callable, Dict, List, Tuple
import pandas as pd
import pytest
import yaml
from suzieq.sqobjects import get_sqobject
from suzieq.sqobjects.basicobj import SqObject
from tests.conftest import TABLES, create_dummy_config_file

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def functions_to_test() -> Dict:
    """Return the list of functions to test read from the test file

    Yields:
        Dict: functions to execute divided by table
    """
    COMMANDS_FILE = 'tests/integration/commands.yml'
    with open(COMMANDS_FILE, 'r') as fp:
        table_cmds = yaml.safe_load(fp)
    yield table_cmds


@pytest.fixture(scope="session")
def gen_config_file() -> str:
    """create a single config file for all tests

    Returns:
        str: path of the config file
    """
    yield create_dummy_config_file()


@pytest.mark.sqobject
@pytest.mark.parametrize("table", [
    pytest.param(table, marks=getattr(pytest.mark, table))
    for table in TABLES])
def test_sqobject_columns(table, functions_to_test, gen_config_file):
    """Test that the columns returned are correct.

    This check is performed both on empty and non-empty dataframes
    """
    table_cmds = functions_to_test
    common_functions = table_cmds['all']
    cfg_file = gen_config_file
    sqobj: SqObject = get_sqobject(table)(config_file=cfg_file)
    table_functions: Dict[str, List[Dict]] = common_functions.copy()
    table_functions.update(table_cmds.get(table, {}))
    for fun, args in table_functions.items():
        if args and args[0] and 'skip' in args[0]:
            # skip means not to run the test
            continue
        compare_results(sqobj, fun, args or [])


def get_exp_cols(sqobj: SqObject, df: pd.DataFrame, fun_args: Dict, fun: str) \
        -> List[str]:
    """Return the set of columns expected by the sqobject

    Returns:
        List[str]: expected columns
    """
    cols = fun_args.get('columns') or ['default']
    if fun == 'get':
        exp_cols = sqobj.schema.get_display_fields(cols)
    elif fun == 'unique':
        exp_cols = fun_args.get('columns', sqobj._unique_def_column.copy())
        if 'count' in fun_args:
            exp_cols.append('numRows')
    elif fun == 'top':
        exp_cols = sqobj.schema.get_display_fields(cols)
        what = fun_args.get('what')
        if what not in exp_cols and cols == ['default']:
            exp_cols.insert(-1, what)
    else:
        if cols != ['default']:
            exp_cols = sqobj.schema.get_display_fields(cols)
        else:
            exp_cols = list(df.columns)
    return exp_cols


def compare_results(sqobj: SqObject, fun: str, fun_args_list: List[Dict]):
    """Execute the function on the sqobject using the args in the fun_args_list
    Then execute the same command adding another argument to receive an
    empty dataframe as result.

    This function checks (for both empty and non empty results):
    - the list of columns is correct
    - the dataframe is not-empty (or empty)
    - if an exception was raised
    - if an error is returned

    Args:
        sqobj (SqObject): sqobject to test
        fun (str): name of the function to test
        fun_args_list (List[Dict]): list of function arguments to test
    """
    table = sqobj.table
    sq_fun = getattr(sqobj, fun)
    for i, fun_args in enumerate(fun_args_list):
        fun_name = f'{table}.{sq_fun.__name__}({i})'
        fun_args = fun_args or {}
        # columns may be updated in the sqobject
        # need to copy to keep the original value
        restore_columns = 'columns' in fun_args
        columns = fun_args.get('columns', []).copy()
        non_empty_res, non_empty_exc = run_function(sq_fun, **fun_args)
        if non_empty_exc:
            pytest.fail(f'{fun_name} exception '
                        f'(non-empty): {non_empty_exc}')
        fun_args.pop('hostname', None)
        if restore_columns:
            fun_args['columns'] = columns.copy()
        empty_res, empty_exc = run_function(
            sq_fun, **fun_args, hostname=['invalid'])
        if empty_exc:
            pytest.fail(f'{fun_name} exception (empty): '
                        f'{empty_exc}')
        if restore_columns:
            fun_args['columns'] = columns.copy()
        if table == 'topology':
            check_topology_results(sqobj, non_empty_res,
                                   empty_res, fun_args, fun, fun_name)
        else:
            exp_cols = get_exp_cols(sqobj, non_empty_res, fun_args, fun)
            exp_empty_cols = exp_cols if fun != 'summarize' else []
            check_results(non_empty_res, empty_res,
                          fun_name, exp_cols, exp_empty_cols)


def check_results(
        non_empty_res: pd.DataFrame,
        empty_res: pd.DataFrame,
        fun_name: str,
        exp_cols: List[str],
        exp_empty_cols: List[str],
):
    """Perform a set of checks to compre the calculated dataframes

    Args:
        non_empty_res (pd.DataFrame): non empty dataframe
        empty_res (pd.DataFrame): empty dataframe
        fun_name (str): name of the function to show in the errors
        exp_cols (List[str]): list of columns expected in non_empty_res
        exp_empty_cols (List[str]): list of columns expected in empty_res
    """
    non_empty_cols = list(non_empty_res.columns)
    empty_cols = list(empty_res.columns)
    if 'error' in empty_res.columns and len(empty_res.columns) == 1:
        pytest.fail(f'{fun_name} error (empty): {empty_res["error"]}')
    elif ('error' in non_empty_res.columns and
            len(non_empty_res.columns) == 1):
        pytest.fail(f'{fun_name} error (non-empty): {non_empty_res["error"]}')
    elif not empty_res.empty:
        pytest.fail(f'{fun_name} was not empty')
    elif non_empty_res.empty:
        pytest.fail(f'{fun_name} was empty')
    elif non_empty_cols != exp_cols:
        pytest.fail(f'{fun_name} (non-empty) got '
                    f'{non_empty_cols}, expected {exp_cols}')
    elif empty_cols != exp_empty_cols:
        pytest.fail(f'{fun_name} (empty) got '
                    f'{empty_cols}, expected {exp_cols}')


def check_topology_results(
        sqobj: SqObject,
        non_empty_res: pd.DataFrame,
        empty_res: pd.DataFrame,
        fun_args: Dict,
        fun: str,
        fun_name: str
):
    """Prepare the expected columns for the check_results function

    Args:
        sqobj (SqObject): sqobject
        non_empty_res (pd.DataFrame): non empty dataframe
        empty_res (pd.DataFrame): empty dataframe
        fun_args (Dict): argument used in the function execution
        fun (str): function executed
        fun_name (str): function name to show in the errors
    """
    if fun == 'get':
        # the 'default' columns for topology depends on the selected via.
        # it's not possible to use the schema to get the expected columns
        columns = fun_args.get('columns', ['*'])
        exp_cols = sqobj.schema.get_display_fields(columns)
        if columns == ['*']:
            via = fun_args.get('via', ['bgp', 'ospf', 'lldp'])
            drop_cols = []
            if 'lldp' not in via:
                drop_cols += ['lldp']
            if 'bgp' not in via:
                drop_cols += ['asn', 'peerAsn', 'bgp']
            if 'ospf' not in via:
                drop_cols += ['area', 'ospf']
            if 'arpnd' not in via:
                drop_cols += ['arpnd', 'arpndBidir']

            if via == ['bgp']:
                drop_cols.append('ifname')

            if drop_cols:
                exp_cols = [c for c in exp_cols if c not in drop_cols]

    else:
        exp_cols = get_exp_cols(sqobj, non_empty_res, fun_args, fun)
    exp_empty_cols = exp_cols if fun != 'summarize' else []
    check_results(non_empty_res, empty_res, fun_name, exp_cols, exp_empty_cols)


def run_function(sq_fun: Callable, **kwargs) -> Tuple[pd.DataFrame, Exception]:
    """Executed the function

    Args:
        sq_fun (Callable): function to execute

    Returns:
        Tuple[pd.DataFrame, Exception]: returns the dataframe (or None if an
        exception occurred) and the exception (or None if no exception is
        captured)
    """
    df: pd.DataFrame = None
    exc: Exception = None
    try:
        df = sq_fun(**kwargs)
    except Exception as e:
        exc = e
    return (df, exc)
