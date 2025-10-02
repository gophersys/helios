import logging
import os
from flask import Blueprint, jsonify, request

# Flask Route
devices_alpha_algo_update_bp = Blueprint("devices_alpha_algo_update", __name__)

# Path to the .msbl file
FILE_PATH = "algo.msbl"

# Define the chunk sizes
FIRST_PAGE_SIZE = 8283  # Total bytes for the first page (metadata + page)
NORMAL_PAGE_SIZE = 8208  # Bytes for every other page

# Define target byte index for logging
TARGET_BYTE_INDEX = 0x44


def hexdump(data, length=16, sep="."):
    """
    Function to produce a hex dump similar to Zephyr's LOG_HEXDUMP_INF
    """
    lines = []
    for i in range(0, len(data), length):
        sub_data = data[i : i + length]
        hex_str = " ".join(f"{b:02x}" for b in sub_data)
        printable_str = "".join(chr(b) if 32 <= b < 127 else sep for b in sub_data)
        lines.append(f"{i:04x}  {hex_str:<{length*3}}  {printable_str}")
    return "\n".join(lines)


@devices_alpha_algo_update_bp.route("/v1/devices/alpha/algo/update", methods=["POST"])
def devices_alpha_algo_update_handler():
    try:
        # Get JSON payload from request
        data = request.json

        if "action" not in data:
            return jsonify({"error": "Bad request, missing action in payload."}), 400

        action = data["action"]

        if action == "file_info":
            # Client is requesting file information
            file_size = os.path.getsize(FILE_PATH)
            total_chunks = (file_size - FIRST_PAGE_SIZE + NORMAL_PAGE_SIZE - 1) // NORMAL_PAGE_SIZE + 1

            file_info = {"file_size": file_size, "file_pages": total_chunks}
            return jsonify(file_info), 200

        elif action == "get_page":
            # Client is requesting a specific page
            if "page_index" not in data:
                return jsonify({"error": "Bad request, missing page_index in payload."}), 400

            page_index = data["page_index"]

            if page_index < 0:
                return jsonify({"error": "Bad request, invalid page_index."}), 400

            # Determine the size of the requested page
            if page_index == 0:
                page_size = FIRST_PAGE_SIZE
            else:
                page_size = NORMAL_PAGE_SIZE

            # Calculate byte range for the requested page
            start_byte = page_index * NORMAL_PAGE_SIZE if page_index > 0 else 0
            end_byte = start_byte + page_size

            # Ensure we don't read beyond the file size
            file_size = os.path.getsize(FILE_PATH)
            if end_byte > file_size:
                end_byte = file_size

            # Read the specific page from the file
            with open(FILE_PATH, "rb") as file:
                file.seek(start_byte)
                page_data = file.read(end_byte - start_byte)

            # Log the value at byte 0x44 for comparison
            if page_index == 0 and TARGET_BYTE_INDEX < len(page_data):
                byte_value_at_0x44 = page_data[TARGET_BYTE_INDEX]
                logging.info(f"Value at byte 0x44 on server side: {byte_value_at_0x44}")

                # Log the first 64 bytes in hex dump format
                logging.info(f"First 64 bytes of chunk:\n{hexdump(page_data[:64])}")

            # Return the page data as a response
            return page_data, 200

        else:
            return jsonify({"error": "Bad request, unknown action."}), 400

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
