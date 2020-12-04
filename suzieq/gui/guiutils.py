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
