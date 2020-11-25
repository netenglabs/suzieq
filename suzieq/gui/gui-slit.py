from suzieq.sqobjects import *
import streamlit as st
import pandas as pd

# df['prefix'] = df.prefix.astype(str)


def get_df(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    columns = kwargs.get('columns', 'default')
    df = sqobject(view=view).get(**kwargs)
    if not (columns == ['all'] or columns == ['default']):
        return df[columns]
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

    st.title('Suzieq')
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
        'routes': routes.RoutesObj
    }

    (table, view, filter, columns) = sidebar(sqobj.keys())
    df = get_df(sqobj[table], view=view, columns=columns)

    if not df.empty:
        if filter:
            df1 = df.query(filter)
        else:
            df1 = df
        st.write(f'<h2>{table} View</h2>', unsafe_allow_html=True)
        clicked = st.button('Summarize')
        convert_dict = {x: 'str' for x in df.select_dtypes('category').columns}
        if table == 'routes':
            df1['prefix'] = df1.prefix.astype(str)
        elif table == 'macs':
            df1.drop(columns=['mackey'], inplace=True)
        st.dataframe(data=style(df1.astype(convert_dict), table),
                     height=600, width=2500)
        st.sidebar.subheader(f'{table} column names')
        st.sidebar.table(tables.TablesObj().describe(
            table=table).style.hide_index())


if __name__ == '__main__':
    _main()
