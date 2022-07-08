import pytest

from suzieq.poller.worker.inventory.inventory import CommandPacer


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
def test_pacer_init():
    """Test the initialization of the command pacer object
    """
    cp = CommandPacer(0)
    assert cp.max_cmds == 0, 'Not expected command pacer max cmds value'
    assert cp._cmd_mutex is None, 'Mutex should\'ve been None'
    assert cp._cmd_semaphore is None, 'Semaphore should\'ve been None'

    ##
    # 2. Test with a value of maximum number of commands
    ##
    max_value = 2
    cp = CommandPacer(max_value)
    assert cp.max_cmds == max_value, 'Not expected max cmds value'
    assert cp._cmd_mutex is not None, 'Mutex shouldn\'t be None'
    assert cp._cmd_semaphore is not None, 'Semaphore shouldn\'t been None'
    assert cp._cmd_semaphore._value == max_value, 'Unexpected semaphore value'
    assert cp._cmd_pacer_sleep == float(1 / max_value), \
        'Unexpected pacer sleep value'
