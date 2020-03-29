from suzieq.poller.services.service import Service


class TopCpuService(Service):

    def clean_data(self, processed_data, raw_data):

        for entry in processed_data:
            for i in ["virtualMem", "residentMem", "cacheMem", "usedMem",
                      "totalMem", "freeMem"]:
                try:
                    entry[i] = int(entry[i])
                except ValueError:
                    if entry[i].endswith("g"):
                        val = float(entry[i].split("g")[0])*1000000
                        entry[i] = int(val)
        return super().clean_data(processed_data, raw_data)
