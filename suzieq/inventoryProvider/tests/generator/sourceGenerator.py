from faker import Faker
from abc import abstractmethod


class SourceGenerator:
    def __init__(self, name, fake: Faker, src_info) -> None:
        pass

    @abstractmethod
    def generate():
        pass
