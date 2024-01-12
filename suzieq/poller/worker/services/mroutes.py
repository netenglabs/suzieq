from suzieq.poller.worker.services.service import Service


class MroutesService(Service):
    """Mroutes service."""

    def _fix_ipvers(self, entry):
        """Fix IP version of entry"""
        if ":" in entry["group"]:
            entry["ipvers"] = 6
        else:
            entry["ipvers"] = 4

    def _fix_star_source(self, entry):
        """Make 0.0.0.0 source a * as convention."""
        if entry["source"] and "0.0.0.0" in entry["source"]:
            entry["source"] = "*"

    def _common_data_cleaner(self, processed_data, _):
        for entry in processed_data:
            self._fix_ipvers(entry)
            self._fix_star_source(entry)

        return processed_data

    def _clean_nxos_data(self, processed_data, _):
        return processed_data
