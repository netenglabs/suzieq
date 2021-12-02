from suzieq.poller.writers.output_worker import OutputWorker


class GatherOutputWorker(OutputWorker):
    """GatherOutputWorker is used to write poller output
    in the case of the run-once data gather mode
    """

    def write_data(self, data):
        file = f"{self.root_output_dir}/{data['topic']}.output"
        with open(file, 'a') as f:
            # Even though we use JSON dump, the output is not valid JSON
            f.write(data['records'])
