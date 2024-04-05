import json
from typing import Dict
from pprint import pprint

def get_json_response(filename: str):
    with open(filename, "r") as f:
        response_json = json.load(f)
    return response_json

def generate_mock_urls(filter: Dict = None, ssl_verify: bool = False) -> Dict:
    """Generates mock urls and their associated response data.
    
    Args:
        filter (Dict): filter criteria
    """
    def get_json_response(filename: str):
        with open(filename, "r") as f:
            response_json = json.load(f)
        return response_json
    protocol = "http:" if not ssl_verify else "https:"
    urls = {}
    urls[f"{protocol}//127.0.0.1:8080/api/"] = get_json_response("responses/base_response.json")
    # if not filter:
    all_devices = get_json_response("responses/all_devices.json")
    # urls[f"{protocol}//127.0.0.1:8080/api/dcim/devices/"] = all_devices
    # for device in all_devices["results"]:
    #     urls[device["primary_ip4"]["url"]] = get_json_response("responses/" + device["name"] + "_ip.json")
    #     urls[device["location"]["url"]] = get_json_response("responses/" + device["name"] + "_location.json")

    return urls


def generate_expected_result(response_data: Dict) -> Dict:
    """Generates expected results based on provided Nautobot response dict.
    
    Args:
        response_data (Dict): sample Nautobot API response dict
    """
    pass