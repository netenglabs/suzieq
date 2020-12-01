from suzieq.sqobjects import *
import streamlit as st
import pandas as pd
from PIL import Image
import altair as alt
import suzieq.gui.SessionState as SessionState


def get_df(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    columns = kwargs.get('columns', 'default')
    df = sqobject(view=view).get(**kwargs)
    if not (columns == ['all'] or columns == ['default']):
        return df[columns]
    return df


def summarize_df(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    df = sqobject(view=view).summarize(**kwargs)
    return df


def unique_df(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    df = sqobject().unique(**kwargs)
    return df


def color_row(row, **kwargs):
    """Color the appropriate column red if the status has failed"""
    fieldval = kwargs.pop("fieldval", "down")
    field = kwargs.pop("field", "state")
    color = kwargs.pop("color", "red")
    if row[field] == fieldval:
        return [f"background-color: {color}"]*len(row)
    else:
        return [""]*len(row)


def color_element_red(value, **kwargs):
    fieldval = kwargs.pop("fieldval", "down")
    if value in fieldval:
        return "color: green"
    else:
        return "color: red"


def style(df, table):
    """Apply appropriate styling for the dataframe based on the table"""
    if table == 'bgp' and 'state' in df.columns:
        return df.style.applymap(color_element_red, fieldval=['Established'],
                                 subset=pd.IndexSlice[:, ['state']])
    elif table == 'ospf' and 'adjState' in df.columns:
        return df.style.applymap(color_element_red,
                                 fieldval=["full", "passive"],
                                 subset=pd.IndexSlice[:, ['adjState']])
    elif table == "routes" and 'prefix' in df.columns:
        return df.style.apply(color_row, axis=1, fieldval='0.0.0.0/0',
                              field='prefix', color='yellow')
    elif table == "interfaces" and 'state' in df.columns:
        return df.style.applymap(color_element_red, fieldval=["up"],
                                 subset=pd.IndexSlice[:, ['state']])
    else:
        return df


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
    columns = st.sidebar.multiselect('View columns',
                                     ['default', 'all'] + fields.name.tolist(),
                                     default='default'
                                     )

    query = st.sidebar.text_input(
        'Filter results with pandas query', value='', key=table)
    st.sidebar.markdown(
        "[query syntax help](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html)")

    if columns == 'all':
        columns = '*'

    return (namespace, hostname, table, view, query, columns)


def _main():

    # Retrieve data from prev session state
    state = SessionState.get(summarized=False, unique=False,
                             summ_button_text='Summarize', prev_table='',
                             clear_query=False, summ_key=0)

    title_container = st.beta_container()
    col1, col2 = st.beta_columns([1, 20])
    image = Image.open('/home/ddutt/Pictures/Suzieq-logo-2.jpg')
    with title_container:
        with col1:
            st.image(image, width=64)
        with col2:
            st.markdown('<h1 style="color: purple;">Suzieq</h1>',
                        unsafe_allow_html=True)

    _max_width_()

    sqobj = {
        'address': address.AddressObj,
        'arpnd': arpnd.ArpndObj,
        'bgp': bgp.BgpObj,
        'device': device.DeviceObj,
        'interfaces': interfaces.IfObj,
        'lldp': lldp.LldpObj,
        'macs': macs.MacsObj,
        'ospf': ospf.OspfObj,
        'routes': routes.RoutesObj,
        'vlan': vlan.VlanObj
    }

    (namespace, hostname, table,
     view, query_str, columns) = sidebar(sqobj.keys(), state.prev_table)

    if state.prev_table != table:
        state.summarized = False
        state.unique = False
        state.summ_button_text = 'Summarize'
        state.prev_table = table
        state.clear_query = True

    df = get_df(sqobj[table], namespace=namespace.split(), hostname=hostname.split(),
                view=view, columns=columns) \
        .reset_index(drop=True)

    if not df.empty:
        if query_str:
            df1 = df.query(query_str)
        else:
            df1 = df

    if not df1.empty:
        st.write(
            f'<h2 style="color: darkblue; font-weight: bold;">{table} View</h2>',
            unsafe_allow_html=True)
        if df.shape[0] > 256:
            st.write(
                'First 256 rows only, use query to look for more specific info')

        buttons = st.beta_container()
        col1, col2, col3 = st.beta_columns([2, 6, 10])
        with buttons:
            with col1:
                placeholder1 = st.empty()
                clicked = placeholder1.button(state.summ_button_text,
                                              key=state.summ_key)
            with col2:
                placeholder3 = st.empty()
                uniq_clicked = placeholder3.selectbox(
                    'Unique', options=['-'] + df.columns.tolist())

        summ_df = pd.DataFrame()
        if clicked:

            if not state.summarized:
                summ_df = summarize_df(sqobj[table], namespace=namespace.split(),
                                       hostname=hostname.split(), view=view)
                state.summarized = True
                state.summ_key += 1
                state.summ_button_text = 'Unsummarize'
                placeholder1.button(state.summ_button_text, key=state.summ_key)
            else:
                summ_df = pd.DataFrame()
                state.summarized = False
                state.summ_key += 1
                state.summ_button_text = 'Summarize'
                placeholder1.button(state.summ_button_text, key=state.summ_key)
        elif state.summarized:
            summ_df = summarize_df(sqobj[table], namespace=namespace.split(),
                                   hostname=hostname.split(), view=view)
            state.summarized = True
            state.summ_button_text = 'Unsummarize'

        summary = st.beta_container()
        dfcols = df.columns.tolist()
        if table == 'routes':
            dfcols.append('prefixlen')

        scol1, scol2 = st.beta_columns(2)

        if uniq_clicked != '-':
            uniq_df = unique_df(sqobj[table], namespace=namespace.split(),
                                hostname=hostname.split(), columns=[uniq_clicked])
        else:
            uniq_df = pd.DataFrame()

        with summary:
            if not summ_df.empty:
                with scol1:
                    st.dataframe(data=summ_df)

            if not uniq_df.empty:
                with scol2:
                    chart = alt.Chart(uniq_df,
                                      title=f'{uniq_clicked} Distribution') \
                        .mark_bar(color='purple',
                                  tooltip=True) \
                        .encode(y=f'{uniq_clicked}:N', x='count')
                    st.altair_chart(chart)

        expander = st.beta_expander('Result', expanded=True)
        with expander:
            convert_dict = {
                x: 'str' for x in df.select_dtypes('category').columns}
            st.dataframe(data=style(df1.head(256).astype(convert_dict), table),
                         height=600, width=2500)
            st.sidebar.subheader(f'{table} column names')
            st.sidebar.table(tables.TablesObj().describe(
                table=table).style.hide_index())
    else:
        expander = st.beta_expander('Result', expanded=True)
        with expander:
            st.markdown('<h2>No Data from query</h2>', unsafe_allow_html=True)


if __name__ == '__main__':
    _main()
