from typing import List
from suzieq.gui.stlit.pagecls import SqGuiPage


def get_menu_pages() -> List[str]:
    '''Return a list of page names to be included in the menu

    Returns:
        List[str]: sorted list of all page names
    '''
    pages = SqGuiPage.get_plugins()
    return sorted([key for key, obj in pages.items() if obj.add_to_menu])


def get_page(page_name: str):
    '''Return the object associated with the page requested

    :param page_name: str, page name for which object is requested
    :returns:
    :rtype: The child class of SqGuiPage that corresponds to the page
            or raises ModuleNotFoundError if the table is not found

    '''

    pages = SqGuiPage.get_plugins()
    if page_name not in pages:
        raise ModuleNotFoundError(f'Page {page_name} not found')

    return pages[page_name]


__all__ = ['get_menu_pages', 'get_page']
