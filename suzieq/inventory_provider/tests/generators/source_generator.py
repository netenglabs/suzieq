from faker import Faker
from abc import abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class SourceGenerator(SqPlugin):
    def __init__(self, name, fake: Faker, src_info) -> None:
        pass

    @abstractmethod
    def generate(self):
        pass
