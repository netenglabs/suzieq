import streamlit as st
import base64


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


def display_title(pagelist):
    '''Render the logo and the app name'''

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
            width: 20%;
            height: auto;
            float:right;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    title_container = st.beta_container()
    title_col, mid, page_col = st.beta_columns([2, 1, 2])
    with title_container:
        with title_col:
            st.markdown(
                f"""
                <div class="container">
                    <img class="logo-img" src="data:image/png;base64,{base64.b64encode(open(LOGO_IMAGE, "rb").read()).decode()}">
                    <h1 style='color:purple;'>Suzieq</h1>
                </div>
                """,
                unsafe_allow_html=True
            )
        with page_col:
            # The empty writes are for aligning the pages link with the logo
            st.text(' ')
            st.text(' ')
            page = st.radio('Page', pagelist)

    return page


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
