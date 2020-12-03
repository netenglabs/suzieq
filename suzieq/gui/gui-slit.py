from suzieq.sqobjects import *
import streamlit as st
import pandas as pd
from PIL import Image
import altair as alt
import suzieq.gui.SessionState as SessionState
import base64


@st.cache(ttl=90)
def get_df(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', 'default')
    if columns == ['all']:
        columns = ['*']
    df = sqobject(view=view).get(columns=columns, **kwargs)
    if not (columns == ['*'] or columns == ['default']):
        return df[columns]
    return df


def run_summarize(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    df = sqobject(view=view).summarize(**kwargs)
    return df


def run_unique(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().unique(**kwargs)
    if not df.empty:
        df.sort_values(by=['count'], inplace=True)
    return df


def run_assert(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().aver(status="fail", **kwargs)
    if not df.empty:
        df.rename(columns={'assert': 'status'}, inplace=True, errors='ignore')
    return df


def color_row(row, **kwargs):
    """Color the appropriate column red if the status has failed"""
    fieldval = kwargs.pop("fieldval", "down")
    field = kwargs.pop("field", "state")
    color = kwargs.pop("color", "black")
    bgcolor = kwargs.pop("bgcolor", "yellow")
    if row[field] == fieldval:
        return [f"background-color: {bgcolor}; color: {color}"]*len(row)
    else:
        return [""]*len(row)


def color_element_red(value, **kwargs):
    fieldval = kwargs.pop("fieldval", "down")
    if value not in fieldval:
        return "background-color: red; color: white;"


def style(df, table, is_assert=False):
    """Apply appropriate styling for the dataframe based on the table"""

    if is_assert:
        if not df.empty:
            return df.style.apply(color_row, axis=1, field='status',
                                  fieldval='fail', bgcolor='darkred',
                                  color='white')
        else:
            return df

    if table == 'bgp' and 'state' in df.columns:
        return df.style.hide_index() \
            .applymap(color_element_red, fieldval=['Established'],
                      subset=pd.IndexSlice[:, ['state']])
    elif table == 'ospf' and 'adjState' in df.columns:
        return df.style.hide_index() \
            .applymap(color_element_red,
                      fieldval=["full", "passive"],
                      subset=pd.IndexSlice[:, ['adjState']])

    elif table == "routes" and 'prefix' in df.columns:
        return df.style.hide_index() \
            .apply(color_row, axis=1, fieldval='0.0.0.0/0',
                   field='prefix')
    elif table == "interfaces" and 'state' in df.columns:
        return df.style.hide_index() \
                       .applymap(color_element_red, fieldval=["up"],
                                 subset=pd.IndexSlice[:, ['state']])
    else:
        return df.style.hide_index()


def _max_width_():
    max_width_str = "max-width: 2000px;"
    st.markdown(
        f"""
    <style>
    .reportview-container .main .block-container{{
        {max_width_str}
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def sidebar(table_values, prev_table):
    """Configure sidebar"""

    namespace = st.sidebar.text_input('Namespace', value='')
    hostname = st.sidebar.text_input('Hostname', value='')
    table = st.sidebar.selectbox(
        'Select Table to View', tuple(table_values))
    view = st.sidebar.radio("View of Data", ('latest', 'all'))
    fields = tables.TablesObj().describe(table=table)
    # columns = st.sidebar.text_input(
    #    "Columns to View (default, all or space separated list)",
    #    value='default')

    colist = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                            fields.name.tolist())))
    columns = st.sidebar.multiselect('Pick columns',
                                     ['default', 'all'] + colist,
                                     default='default')
    if ('default' in columns or 'all' in columns) and len(columns) == 1:
        col_sel_val = True
    else:
        col_sel_val = False

    col_ok = st.sidebar.checkbox('Column Selection Done', value=col_sel_val)
    if not col_ok:
        columns = ['default']

    if not columns:
        columns = ['default']

    if table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
        assert_clicked = st.sidebar.checkbox('Run Assert', value=False)
    else:
        assert_clicked = False

    if not col_ok:
        st.stop()
    if ('default' in columns or 'all' in columns) and len(columns) != 1:
        st.error('Cannot select default/all with any other columns')
        st.stop()
    elif not columns:
        st.error('Columns cannot be empty')
        st.stop()

    query = st.sidebar.text_input(
        'Filter table show results with pandas query', value='', key=table)
    st.sidebar.markdown(
        "[query syntax help](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html)")

    if columns == 'all':
        columns = '*'

    col_expander = st.sidebar.beta_expander('Column Names', expanded=False)
    with col_expander:
        st.subheader(f'{table} column names')
        st.table(tables.TablesObj().describe(table=table)
                 .query('name != "sqvers"')
                 .reset_index(drop=True).style)

    return (namespace, hostname, table, view, query, assert_clicked, columns)


def _hide_index():
    '''CSS to hide index'''
    st.markdown("""
    <style>
    table td:nth-child(1) {
        display: none
    }
    table th:nth-child(1) {
        display: none
    }
    </style>
    """, unsafe_allow_html=True)


def print_title():
    '''Print the logo and the heading'''

    LOGO_IMAGE = 'logo-small.png'
    st.markdown(
        """
        <style>
        .container {
            display: flex;
        }
        .logo-text {
            font-weight:700 !important;
            font-size:24px !important;
            color: purple !important;
            padding-top: 40px !important;
        }
        .logo-img {
            width: 10%;
            height: auto;
            float:right;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="container">
            <img class="logo-img" src="data:image/png;base64,{base64.b64encode(open(LOGO_IMAGE, "rb").read()).decode()}">
            <h1 style='color:purple;'>Suzieq</h1>
        </div>
        """,
        unsafe_allow_html=True
    )


def _main():

    # Retrieve data from prev session state
    state = SessionState.get(prev_table='', clear_query=False)

    st.set_page_config(layout="wide")
    _hide_index()
    print_title()

    # TOODO: Build tables from list rather than manually
    sqobj = {
        'address': address.AddressObj,
        'arpnd': arpnd.ArpndObj,
        'bgp': bgp.BgpObj,
        'device': device.DeviceObj,
        'evpnVni': evpnVni.EvpnvniObj,
        'fs': fs.FsObj,
        'interfaces': interfaces.IfObj,
        'lldp': lldp.LldpObj,
        'macs': macs.MacsObj,
        'mlag': mlag.MlagObj,
        'ospf': ospf.OspfObj,
        'routes': routes.RoutesObj,
        'sqpoller': sqPoller.SqPollerObj,
        'vlan': vlan.VlanObj
    }

    (namespace, hostname, table, view,
     query_str, assert_clicked, columns) = sidebar(sqobj.keys(), state.prev_table)

    if state.prev_table != table:
        state.prev_table = table
        state.clear_query = True

    df = get_df(sqobj[table], namespace=namespace.split(),
                hostname=hostname.split(),
                view=view, columns=columns) \
        .reset_index(drop=True)

    df1 = df
    if not df.empty:
        if query_str:
            df1 = df.query(query_str)

    if not df1.empty:
        st.write(
            f'<h2 style="color: darkblue; font-weight: bold;">{table} View</h2>',
            unsafe_allow_html=True)
        if df.shape[0] > 256:
            st.write(
                'First 256 rows only, use query to look for more specific info')

        dfcols = df.columns.tolist()
        if table == 'routes':
            dfcols.append('prefixlen')

        dfcols = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                                dfcols)))

        uniq_clicked = st.selectbox(
            'Distribution Count of', options=['-'] + dfcols,
            index=dfcols.index('hostname')+1)

        assert_df = pd.DataFrame()

        scol1, scol2 = st.beta_columns(2)

        if uniq_clicked != '-':
            uniq_df = run_unique(sqobj[table], namespace=namespace.split(),
                                 hostname=hostname.split(), columns=[uniq_clicked])
        else:
            uniq_df = pd.DataFrame()

        summ_df = run_summarize(sqobj[table], namespace=namespace.split(),
                                hostname=hostname.split())

        if assert_clicked:
            assert_df = run_assert(sqobj[table], namespace=namespace.split())
            state.validate = True

        # with summary:
        if not summ_df.empty:
            with scol1:
                st.subheader('Summary Information')
                st.dataframe(data=summ_df)

        if not uniq_df.empty:
            with scol2:
                if uniq_df.shape[0] > 64:
                    st.warning(
                        f'{uniq_clicked} has cardinality > 64. Displaying top 64')
                    chart = alt.Chart(
                        uniq_df.head(64),
                        title=f'{uniq_clicked} Distribution') \
                        .mark_bar(color='purple', tooltip=True) \
                        .encode(y=alt.Y(f'{uniq_clicked}:N', sort='-x'),
                                x='count')
                else:

                    chart = alt.Chart(
                        uniq_df, title=f'{uniq_clicked} Distribution') \
                        .mark_bar(color='purple', tooltip=True) \
                        .encode(y=alt.Y(f'{uniq_clicked}:N', sort='-x'),
                                x='count')
                st.altair_chart(chart)

        if table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
            if assert_df.empty:
                expand_assert = False
            else:
                expand_assert = True
            validate_expander = st.beta_expander('Assert',
                                                 expanded=expand_assert)
            with validate_expander:
                if not assert_df.empty:
                    st.dataframe(data=assert_df)
                elif state.validate or assert_clicked:
                    st.write('Assert passed')

        expander = st.beta_expander('Table', expanded=True)
        with expander:
            convert_dict = {
                x: 'str' for x in df.select_dtypes('category').columns}
            st.dataframe(data=style(df1.head(256).astype(convert_dict), table),
                         height=600, width=2500)
    else:
        expander = st.beta_expander('Table', expanded=True)
        with expander:
            st.markdown('<h2>No Data from query</h2>', unsafe_allow_html=True)


if __name__ == '__main__':
    _main()
