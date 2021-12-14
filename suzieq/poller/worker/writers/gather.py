"""
This module contains the logic of the writer for the 'gather' mode
"""
import os

from suzieq.poller.worker.writers.output_worker import OutputWorker


class GatherOutputWorker(OutputWorker):
    """GatherOutputWorker is used to write poller output
    in the case of the run-once data gather mode
    """

    def write_data(self, data):
        """Write the output of the commands into a plain file

        Args:
            data (Dict): dictionary containing the data to store.
        """
        file = os.path.join(self.root_output_dir, f"{data['topic']}.output")
        with open(file, 'a') as f:
            # Even though we use JSON dump, the output is not valid JSON
            f.write(data['records'])
