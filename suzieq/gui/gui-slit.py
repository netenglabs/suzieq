from suzieq.sqobjects import *
import streamlit as st
import pandas as pd
from PIL import Image
import altair as alt


# df['prefix'] = df.prefix.astype(str)


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


def sidebar(table_values):
    """Configure sidebar"""

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
    filter = st.sidebar.text_input(
        'Filter results with pandas query', value='')
    st.sidebar.markdown(
        "[query syntax help](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html)")

    if columns == 'all':
        columns = '*'

    return table, view, filter, columns


def _main():

    title_container = st.beta_container()
    col1, col2 = st.beta_columns([1, 20])
    image = Image.open('/home/ddutt/Pictures/Suzieq-logo-2.jpg')
    with title_container:
        with col1:
            st.image(image, width=64, use_column_width=False)
        with col2:
            st.markdown('<h1 style="color: purple;">Suzieq</h1>',
                        unsafe_allow_html=True)

    _max_width_()
    summarized = unique = False

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

    (table, view, filter, columns) = sidebar(sqobj.keys())
    df = get_df(sqobj[table], view=view, columns=columns)

    if not df.empty:
        if filter:
            df1 = df.query(filter)
        else:
            df1 = df

    if not df1.empty:
        st.write(f'<h2>{table} View</h2>', unsafe_allow_html=True)
        if df.shape[0] > 256:
            st.write(
                'First 256 rows only, use query to look for more specific info')

        buttons = st.beta_container()
        col1, col2, col3 = st.beta_columns([2, 6, 10])
        with buttons:
            with col1:
                placeholder1 = st.empty()
                clicked = placeholder1.button('Summarize')
            with col2:
                placeholder3 = st.empty()
                uniq_clicked = placeholder3.selectbox(
                    'Unique', options=['-'] + df.columns.tolist())

        if clicked and not summarized:
            df1 = summarize_df(sqobj[table], view=view)
            summarized = True
            clicked = placeholder1.button('Unsummarize')
        elif clicked == 'Unsummarize' and summarized:
            summarized = True
            clicked = placeholder1.button('Summarize')

        if uniq_clicked != '-' and not unique:
            uniq_df = unique_df(sqobj[table], columns=[uniq_clicked])
            chart = alt.Chart(uniq_df).mark_bar(color='purple').encode(
                y=uniq_clicked, x='count')
            with buttons:
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
