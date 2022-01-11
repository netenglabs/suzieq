import pytest
from suzieq.poller.controller.chunker.static import StaticChunker
from suzieq.shared.exceptions import SqPollerConfError
from tests.unit.poller.shared.utils import read_yaml_file

_POLICIES = ['sequential', 'namespace']
_N_CHUNKS = [1, 2, 3]
_DATA_DIR = 'tests/unit/poller/controller/chunker/data/static'


_GLOB_INV = read_yaml_file(f'{_DATA_DIR}/inventory.yaml')


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_chunker
@pytest.mark.controller_chunker_static
@pytest.mark.parametrize('policy', _POLICIES)
@pytest.mark.parametrize('n_chunks', _N_CHUNKS)
def test_split(policy: str, n_chunks: int):
    """Test the chunks are build correctly

    Args:
        policy (str): chunking policy
        n_chunks (int): number of chunks
    """
    ch = StaticChunker({'policy': policy})
    assert ch.policy == policy

    chunks = ch.chunk(_GLOB_INV, n_chunks)

    res_path = f'{_DATA_DIR}/results/{policy}_{n_chunks}.yaml'
    assert chunks == read_yaml_file(res_path)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_chunker
@pytest.mark.controller_chunker_static
def test_default_config():
    """Test that the default configuration is set up
    """
    ch = StaticChunker()
    assert ch.policy == 'sequential'


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_chunker
@pytest.mark.controller_chunker_static
@pytest.mark.parametrize('policy', _POLICIES)
@pytest.mark.parametrize('n_chunks', [10])
def test_too_much_chunks(policy: str, n_chunks: int):
    """If the number of chunks is less than the desired one,
    the chunker will raise an exception

    Example:
    The inventory is composed by 5 nodes and 'n_chunks' is 10,
    there is no way to split 5 devices in 10 chunks

    Args:
        policy (str): chunking policy
        n_chunks (int): number of chunks
    """
    ch = StaticChunker({'policy': policy})

    with pytest.raises(SqPollerConfError):
        ch.chunk(_GLOB_INV, n_chunks)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_chunker
@pytest.mark.controller_chunker_static
def test_unknown_policy():
    """Test that an unknown policy is recognized
    """
    with pytest.raises(SqPollerConfError, match="Unknown chunking policy "
                       "unknown-policy"):
        StaticChunker({'policy': 'unknown-policy'})
