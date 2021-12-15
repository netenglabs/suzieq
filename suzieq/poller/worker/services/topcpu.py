from suzieq.poller.worker.services.service import Service


class TopCpuService(Service):
    '''TopCpu service class'''

    def _common_data_cleaner(self, processed_data, _):

        for entry in processed_data:
            for i in ["virtualMem", "residentMem", "cacheMem", "usedMem",
                      "totalMem", "freeMem"]:
                try:
                    entry[i] = int(entry[i])
                except ValueError:
                    if entry[i].endswith("g"):
                        val = float(entry[i].split("g")[0])*1000000
                        entry[i] = int(val)

        return processed_data
