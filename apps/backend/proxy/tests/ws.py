import json
import logging
import sys

import requests
import socketio

sio = socketio.Client()

PROXY_URL = "localhost"
PROXY_PORT = 9001


def start_test(cluster_uuid, test_uuid) -> str:
    """Make an HTTP request to start the test and obtain a session_id."""
    request = {"config": {}, "nodes": ["slot-1", "slot-2", "slot-3", "slot-4", "slot-5"]}
    response = requests.post(
        f"http://{PROXY_URL}:{PROXY_PORT}/v1/clusters/{cluster_uuid}/tests/{test_uuid}/exec", json=request
    )
    if response.status_code == 202:
        return response.json().get("executionId")
    else:
        logging.error(f"Failed to start the test ({response.status_code}): {response.text}")
        sys.exit(1)


@sio.event
def connect():
    print("Connection established")


@sio.event
def exec_test_response(data):
    print("Received data:")
    print(json.dumps(data, indent=4))

    if data.get("done") or data.get("error"):
        if data.get("error"):
            print(f"Error received: {data['error']}")
        else:
            print(f"Test {data['executionId']} completed successfully.")
        sio.emit("test_complete", data)
        sio.disconnect()


@sio.event
def disconnect():
    print("Disconnected from server")


if __name__ == "__main__":
    try:
        cluster_uuid = "5edcf143-69fd-4511-af56-3dce55ed2eb5"
        test_uuid = "fce7ab74-b225-433d-b27d-629d346548d9"

        # Hit the HTTP route which will return a session id
        session_id = start_test(cluster_uuid, test_uuid)

        print(f"Test {test_uuid} started, session id: {session_id}")

        # Connect to the server
        sio.connect(f"http://{PROXY_URL}:{PROXY_PORT}")
        sio.emit("exec_test", {"session_id": session_id})
        sio.wait()

    except Exception as e:
        logging.error("Failed to connect or run test: {}".format(str(e)))
