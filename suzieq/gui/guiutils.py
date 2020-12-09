import streamlit as st
import pandas as pd


@st.cache(ttl=90, allow_output_mutation=True)
def gui_get_df(sqobject, **kwargs):
    table = kwargs.pop('_table', '')
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    stime = kwargs.pop('start_time', '')
    etime = kwargs.pop('end_time', '')
    if columns == ['all']:
        columns = ['*']
    if table != "tables":
        df = sqobject(view=view, start_time=stime, end_time=etime) \
            .get(columns=columns, **kwargs)
    else:
        df = sqobject(view=view, start_time=stime, end_time=etime) \
            .get(**kwargs)
    if not df.empty:
        df = sqobject().humanize_fields(df)
        if table == 'address':
            if 'ipAddressList' in df.columns:
                df = df.explode('ipAddressList').fillna('')
            if 'ip6AddressList' in df.columns:
                df = df.explode('ip6AddressList').fillna('')
    if not (columns == ['*'] or columns == ['default']):
        return df[columns].reset_index(drop=True)
    return df.reset_index(drop=True)


def maximize_browser_window():
    '''Maximize browser window in streamlit'''

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


def horizontal_radio():
    '''Make the radio buttons horizontal'''
    st.write('<style>div.row-widget.stRadio > div{flex-direction:row;}</style>',
             unsafe_allow_html=True)


def hide_st_index():
    '''CSS to hide table index rendered via st.table'''
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


def sq_gui_style(df, table, is_assert=False):
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
