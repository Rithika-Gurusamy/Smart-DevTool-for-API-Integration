from generators.base import BaseSDKGenerator

class BaseRESTGenerator(BaseSDKGenerator):
    """
    Base class for standalone REST request generators.
    """
    def __init__(self):
        super().__init__()

    def generate_rest(self, api_metadata: dict, use_case: str) -> str:
        raise NotImplementedError
