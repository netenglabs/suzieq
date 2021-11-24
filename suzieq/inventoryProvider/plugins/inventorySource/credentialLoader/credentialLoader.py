from abc import abstractclassmethod


class CredentialLoader:
    def __init__(self, init_data) -> None:
        self.init(init_data)
        pass

    def init(self, init_data):
        pass

    @abstractclassmethod
    def load(self, data):
        pass
