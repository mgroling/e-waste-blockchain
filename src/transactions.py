"""
The following transaction types exist:

    BLOCK:
        This transaction type records the transfer of an item to a new place and has the following format:
        BLOCK=DEVICE-ID=LOCATION=TIMESTAMP=DESTRUCT=SIGNED-DIGEST

        Explanation of attributes:
        BLOCK:                  identifier that this transaction is of the type BLOCK
        DEVICE-ID:              device id
        LOCATION:               name of the site that the item was received
        TIMESTAMP:              timestamp with the format specified in DATETIME_FORMAT
        DESTRUCT:               bool if the item is to be destroyed at that site
        SIGNED-DIGEST:          The signed hash of the data

    ALLOCATE:
        This transaction type allocates a new device id and has the following format:
        ALLOCATE=LOCATION=TIMESTAMP

        location and timestamp are only required to ensure that no two transactions are the same

        It returns the reserved device-id in the deliver_tx method (under data)

The following query types exist:

    HISTORY:
        This query type can be used to retrieve all data of a single device, it has the following format:
        HISTORY=DEVICE-ID

        The data is returned in the following way:
        key                     stores the device-id
        value                   stores all the locations and timestamps, the timestamp is in the format DATETIME_FORMAT
                                these attributes are seperated with =, it could look like this:
                                location1=timestamp1=location2=timestamp2

    NUMBER:
        This query can be used to retrieve how many device ids are assigned, it has the following format:
        NUMBER

        The data is returned in the following way:
        value                   returns the highest device id that is assigned (as such device ids 0..{number returned} are assigned)
"""


from hashlib import sha256
from datetime import datetime
from ecdsa import SigningKey
from typing import Tuple, List
import requests
import json
import base64

BYTE_ENCODING = "UTF-8"
DATETIME_FORMAT = "%y%m%d%H%M%S%f"


def compute_hash(
    device_id: int, location: str, timestamp: datetime, destruct: bool
) -> bytes:
    hasher = sha256()
    hasher.update(bytes(str(device_id), BYTE_ENCODING))
    hasher.update(bytes(location, BYTE_ENCODING))
    hasher.update(bytes(timestamp.strftime(DATETIME_FORMAT), BYTE_ENCODING))
    hasher.update(bytes(str(destruct), BYTE_ENCODING))
    return hasher.digest()


def allocate_device_id(location: str) -> Tuple[bool, int]:
    """
    Send a transaction to the Tendermint network to allocate a new device id

    returns:
        allocation result (indicating success/failure)

        allocated device id
    """
    try:
        response = requests.get(
            'http://localhost:26657/broadcast_tx_commit?tx="ALLOCATE={}={}"'.format(
                location, datetime.now().strftime(DATETIME_FORMAT)
            )
        )
        dict = json.loads(response.content)
        # check if there was an error, while checking the transaction
        if dict["result"]["check_tx"]["code"]:
            return False, -1

        return True, int(
            base64.b64decode(dict["result"]["deliver_tx"]["data"]).decode(BYTE_ENCODING)
        )
    except KeyboardInterrupt:
        quit()
    except:
        return False, -1


def send_device_location(
    device_id: int, location: str, signing_key: SigningKey, destruct: bool
) -> Tuple[bool, str]:
    """
    Send a transaction to the Tendermint network to add a new location for a device with the current time

    returns:
        result (indicating success/failure)

        error message in case of failure
    """
    try:
        now: datetime = datetime.now()
        transaction_string = "BLOCK={}={}={}={}={}".format(
            device_id,
            location,
            now.strftime(DATETIME_FORMAT),
            destruct,
            signing_key.sign(compute_hash(device_id, location, now, destruct)).hex(),
        )
        response = requests.get(
            'http://localhost:26657/broadcast_tx_commit?tx="{}"'.format(
                transaction_string
            )
        )
        dict = json.loads(response.content)

        # check if there was an error, while checking the transaction
        if dict["result"]["check_tx"]["code"]:
            return False, dict["result"]["check_tx"]["log"]

        return True, ""
    except KeyboardInterrupt:
        quit()
    except:
        return (
            False,
            "unexpected error",
        )


def query_number_of_devices() -> Tuple[bool, str, int]:
    """
    Queries the Tendermint network how many device ids are assigned

    returns:
        result (indicating success/failure)

        log about the result (empty if no error occured)

        highest device id that is assigned (as such 0..{returned device id} are assigned)
    """
    try:
        response = requests.get('http://localhost:26657/abci_query?data="NUMBER"')
        dict = json.loads(response.content)
        message = dict["result"]["response"]

        # check if there was an error
        if message["code"]:
            return False, message["log"], -1

        return True, "", int(base64.b64decode(message["value"]).decode(BYTE_ENCODING))
    except KeyboardInterrupt:
        quit()
    except:
        return False, "unexpected error", -1


def query_device_information(
    device_id: int,
) -> Tuple[bool, str, List[Tuple[str, datetime]]]:
    """
    Queries the Tendermint network about the given device-id

    returns:
        result (indicating success/failure)

        info/log about the result

        List of Tuples that store the locations + timestamps that the device was at in chronological order
    """
    try:
        response = requests.get(
            'http://localhost:26657/abci_query?data="HISTORY={}"'.format(device_id)
        )
        dict = json.loads(response.content)
        message = dict["result"]["response"]

        # check if there was an error
        if message["code"]:
            return False, message["log"], []

        device_info = []
        if message["value"]:
            data = base64.b64decode(message["value"]).decode(BYTE_ENCODING).split("=")

            for i in range(0, len(data), 2):
                device_info.append(
                    (data[i], datetime.strptime(data[i + 1], DATETIME_FORMAT))
                )

        return True, message["info"], device_info
    except KeyboardInterrupt:
        quit()
    except:
        return False, "unexpected error", []
