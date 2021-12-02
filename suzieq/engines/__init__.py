
from suzieq.engines.base_engine import SqEngineObj


def get_sqengine(engine_name: str, table_name: str):
    """Return either the top level engine obj or a specific engine obj

    Args:
        engine_name (str): Name of the engine
        table_name (str): Table specific engine object

    Raises:
        Exception: ModuleNotFoundError if the engine is not found

    Returns:
        [class]: SqEngineObj
    """
    engine_obj = SqEngineObj.get_plugins(engine_name).get(engine_name, None)
    if not engine_obj:
        raise ModuleNotFoundError(f"Engine {engine_name} not found")

    if table_name:
        table_obj = engine_obj.get_plugins(table_name).get(table_name, None)
    else:
        table_obj = engine_obj

    if not table_obj:
        raise ModuleNotFoundError(f"Table {table_name} not found for "
                                  f"engine {engine_name}")
    return table_obj


__all__ = ['get_sqengine']
