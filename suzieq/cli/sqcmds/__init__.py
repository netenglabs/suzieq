from os.path import dirname, basename, isfile, join
import glob

name = "sqcmds"

modules = filter(
    lambda f: f
    if isfile(f)
    and not (
        f.endswith("__init__.py")
        or f.endswith("command.py")
        or f.endswith("context_commands.py")
        or f.endswith("TopcpuCmd.py")
        or f.endswith("TopmemCmd.py")
    )
    else None,
    glob.glob(join(dirname(__file__), "*.py")),
)
__all__ = [basename(f)[:-3] for f in modules]

sqcmds_all = __all__
