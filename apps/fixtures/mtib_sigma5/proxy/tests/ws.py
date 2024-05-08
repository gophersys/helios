import socketio
import time
import sys
import logging
import requests

sio = socketio.Client()

def start_test(cluster_uuid, test_uuid):
    """Make an HTTP request to start the test and obtain a session_id."""
    response = requests.post(f'http://127.0.0.1:6969/v1/clusters/{cluster_uuid}/tests/{test_uuid}/exec')
    if response.status_code == 202:
        return response.json().get('session_id')
    else:
        print("Failed to start the test:", response.text)
        return None

@sio.event
def connect():
    print("Connection established")

@sio.event
def server(data):
    print("Received data:", data)
    logging.info("Received data:", data)

@sio.event
def disconnect():
    print("Disconnected from server")

if __name__ == "__main__":
    try:
        # Assume the UUIDs for the cluster and test are known before running the client
        cluster_uuid = 'f24146a0-eca5-400a-b03b-db7c93391b1f'  # Replace with actual cluster UUID
        test_uuid = 'your-test-uuid'  # Replace with actual test UUID

        # Start the test and get a session_id
        session_id = start_test(cluster_uuid, test_uuid)
        if session_id:
            # Connect to the server and join the room with the session_id
            sio.connect('http://127.0.0.1:6969')  # Update with your actual server address and port
            sio.emit('exec_test', {'session_id': session_id})
            time.sleep(100)
        else:
            print("Unable to obtain session_id and start the test.")
    except Exception as e:
        print("Failed to connect or run test:", str(e))
