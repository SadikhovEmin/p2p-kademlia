from enum import Enum


class MessageCodes(Enum):
    DHT_PUT = 650
    DHT_GET = 651
    DHT_SUCCESS = 652
    DHT_FAILURE = 653
