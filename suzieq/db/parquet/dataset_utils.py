import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def move_broken_file(broken_file: str):
    """Move a broken file to a directory to be investigated later

    Args:
        broken_file (str): the path to the broken file.
    """
    broken_file_path = Path(broken_file)
    if broken_file_path.exists():
        # Get the path to the broken file
        splitted_path = broken_file.split('sqvers=')
        if len(splitted_path) == 2:
            table_dir = Path(splitted_path[0])
            outfile = table_dir.parent / '_broken' / table_dir.stem / \
                f"sqvers={splitted_path[1]}"

            logger.warning(
                f'Moving broken file from {broken_file} to {outfile}')
            outfile.parent.mkdir(exist_ok=True, parents=True)
            broken_file_path.rename(outfile)
        else:
            logger.error(
                f'Unable to move broken file {broken_file} wrong file path')
