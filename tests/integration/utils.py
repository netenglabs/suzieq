import pandas as pd
import yaml


class Dict2Class(object):
    def __init__(self, dvar, def_topvar):
        if not isinstance(dvar, dict) or not dvar:
            setattr(self, def_topvar, None)
            return

        for key in dvar:
            if isinstance(dvar[key], list):
                nested_dclass = []
                for ele in dvar[key]:
                    newele = Dict2Class(ele, def_topvar=ele)
                    nested_dclass.append(newele)
                    setattr(self, key.replace('-', '_'), nested_dclass)
            else:
                setattr(self, key.replace('-', '_'), dvar[key])


class Yaml2Class(object):
    def __init__(self, yaml_file, def_topvar='transform'):
        with open(yaml_file, 'r') as f:
            dvar = yaml.safe_load(f.read())
            self.transform = Dict2Class(dvar, def_topvar)


def assert_df_equal(expected_df, got_df, ignore_cols) -> None:
    '''Compare the dataframes for equality

    Comparing data frames is tough. The main thing we're concerned about
    here is that the contents are identical. We're less concerned about the
    order. The reason for the lack of comparison of order is because the
    order could change as a consequence of coalescing or some other change. 

    We work our way from the simplest and fastest attempts to compare equality
    to slower ways to compare equality. Trying to ignore the sort is the hardest
    part. First we attempt to sort the two and reset the index to avoid index
    mismatches. When one of the columns is a list in which case we resort to 
    deriving tuples of the expected and obtained dataframes, stripping the Index
    column (should be a range Index only), and then verifying that a row is 
    present in the other dataframe. We even use sets to attempt a quicker tuple
    comparison which can again fail due to the presence of a list.

    Real failures are hopefully caught quickly while less clear ones are run
    through a wringer to verify that there's a real problem.
    '''

    assert(got_df.shape == expected_df.shape)
    assert((got_df.columns == expected_df.columns).all())
    # We assume the asssert failure prevents the code from continuing

    if (expected_df.empty and got_df.empty):
        return

    # Drop any columns to be ignored
    if ignore_cols:
        if not got_df.empty:
            got_df = got_df.drop(columns=ignore_cols, errors='ignore')
        if not expected_df.empty:
            expected_df = expected_df.drop(
                columns=ignore_cols, errors='ignore')

    try:
        if isinstance(got_df.index, pd.RangeIndex):
            expected_df = expected_df \
                .sort_values(by=expected_df.columns.tolist()) \
                .reset_index(drop=True)
        else:
            expected_df = expected_df \
                .sort_values(by=expected_df.columns.tolist())

        if isinstance(expected_df.index, pd.RangeIndex):
            got_df = got_df.sort_values(by=got_df.columns.tolist()) \
                           .reset_index(drop=True)
        else:
            got_df = got_df.sort_values(by=got_df.columns.tolist())

    except Exception:
        if 'namespace' in expected_df.columns and 'timestamp' in expected_df.columns:
            expected_df = expected_df.sort_values(
                by=['namespace', 'hostname', 'timestamp']).reset_index(drop=True)
            got_df = got_df.sort_values(
                by=['namespace', 'hostname', 'timestamp']).reset_index(drop=True)

    try:
        rslt_df = expected_df.compare(got_df, keep_equal=True)
        if not rslt_df.empty:
            matches = True
            # If there are lists in the values, their order maybe causing
            # the failure. Pass if the problem is the order but they're
            # equal
            for row in rslt_df.itertuples():
                if isinstance(row._1, list) and isinstance(row._2, list):
                    if set(row._1) != set(row._2):
                        matches = False
                        break
                else:
                    matches = False
                    break
            if not matches:
                # This could be because of mismatch in sorted columns
                # We have assured that the shape is identical already, so try a
                # manual compare. Skip the index number in this case,
                # assuming range index, since the sort messes up this order
                if isinstance(got_df.index, pd.RangeIndex):
                    got_tuples = [x[1:] for x in got_df.itertuples()]
                else:
                    got_tuples = [x for x in got_df.itertuples()]
                if isinstance(expected_df.index, pd.RangeIndex):
                    expected_tuples = [x[1:] for x in expected_df.itertuples()]
                else:
                    expected_tuples = [x for x in expected_df.itertuples()]
                try:
                    assert(set(got_tuples) == set(expected_tuples))
                except TypeError:
                    matches = True
                    for item in expected_tuples:
                        if item not in got_tuples:
                            matches = False
                            assert(rslt_df.empty)
            if not matches:
                print(rslt_df)
                assert(rslt_df.empty)
    except ValueError:
        # This happens when the two dataframes don't have the same shape
        # such as what happens if the return is an error. So, compare fails
        # and we have to try a different technique
        try:
            rslt_df = pd.merge(got_df,
                               expected_df,
                               how='outer',
                               indicator=True)
            if not got_df.empty:
                assert(not rslt_df.empty and rslt_df.query(
                    '_merge != "both"').empty)
        except Exception:
            assert(got_df.shape == expected_df.shape)
            assert('Unable to compare' == '')
