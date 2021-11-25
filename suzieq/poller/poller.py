import logging

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, userargs, cfg):
        pass

    async def init_poller(self):
        """Initialize the poller, instantiating the services and setting up
        the connection with the nodes. This function should be called only
        at the beginning before calling run().
        """

        pass

    async def run(self):
        """Start polling the devices.
        Before running this function the poller should be initialized.
        """

        pass

    async def _init_services():
        """Instantiate the services to run in the poller"""
        pass

    async def _add_poller_task(self, task):
        """Add a new task to be executed in the poller run loop."""

        pass

    async def _pop_waiting_poller_tasks(self):
        """Empty the list of tasks to be added in the run loop
        and return its content.
        """

        pass

    def _evaluate_service_list(self):
        """Constuct the list of the name of the services to be started
        in the poller, according to the arguments passed by the user.
        Returns a InvalidAttribute exception if any of the passed service
        is invalid.
        """

        pass

    async def _stop(self):
        """Stop the poller"""

        pass

    def _validate_poller_args(self, userargs, cfg):
        """Validate the arguments and the configuration passed to the poller.
        The function produces a AttributeError exception if there is something
        wrong in the configuration.
        """

        pass
