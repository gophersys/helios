import json
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import matplotlib
import time
import logging

matplotlib.use("Agg")
from src.services.database.schema import ObservabilityMemInfo

# channel = "c0a1d872-84dc-40ea-a196-d07825493566"  # Full Chip Erase
# channel = "be2c53cd-7256-4219-b656-03dbaf52c7b1"  # Virgin chip, format/create file system + 10MB (10 files)  = FAILED
channel = "1e287f02-7ab4-4cc6-9ab8-300b3d5ce833"  # Virgin chip, format/create file system + 10MB (10 files)


def load_observability_data(filepath: str) -> ObservabilityMemInfo:
    with open(filepath, "r") as f:
        data = json.load(f)
    return ObservabilityMemInfo.unmarshal(data)


def map_address_to_array(address, metadata):
    lu_size = metadata.blocks_per_lu * metadata.pages_per_block * metadata.data_bytes_per_page
    lu = address // lu_size
    relative_address = address % lu_size
    block = relative_address // (metadata.pages_per_block * metadata.data_bytes_per_page)
    page = (
        relative_address % (metadata.pages_per_block * metadata.data_bytes_per_page)
    ) // metadata.data_bytes_per_page
    return lu, block, page


def update_memory(memory, operation, metadata, operation_type, operation_tracker):
    lu, block, page = map_address_to_array(operation.address, metadata)

    # Calculate the correct index in the 1D array by combining lu and block
    block_index = lu * metadata.blocks_per_lu + block

    # Ensure indices are within bounds
    if 0 <= block_index < operation_tracker.size and 0 <= page < metadata.pages_per_block:
        if operation_type == "erase":
            if not operation_tracker[block_index]:  # Check and update based on combined index
                memory[block_index, :, :] = [0, 0, 255]  # Set the entire block to pure blue
                operation_tracker[block_index] = True  # Mark this block as erased
        elif operation_type == "write":
            memory[block_index, page, :] = [255, 0, 0]  # Set the page to orange for write
        elif operation_type == "read":
            memory[block_index, page, :] = [0, 255, 0]  # Set the page to green for read
    else:
        print(
            f"Skipping out-of-bounds operation at Address: {operation.address}, LU: {lu}, Block: {block}, Page: {page}"
        )


def create_erase_heatmap_movie(observability_info: ObservabilityMemInfo, output_filepath: str, frame_step: int = 50):
    start_time = time.time()

    metadata = observability_info.metadata
    memory = np.zeros((metadata.blocks_per_lu * metadata.num_lus, metadata.pages_per_block, 3), dtype=np.uint8)
    operation_tracker = np.zeros((metadata.blocks_per_lu * metadata.num_lus), dtype=bool)
    operation_entries = observability_info.operation_entries

    fig, ax = plt.subplots(figsize=(6, 10))

    plt.ioff()  # Turn off interactive mode for better performance
    import matplotlib

    matplotlib.use("Agg")  # Use Agg backend

    canvas_width, canvas_height = fig.canvas.get_width_height()

    cmdstring = (
        "ffmpeg",
        "-y",
        "-r",
        "30",
        "-s",
        f"{canvas_width}x{canvas_height}",
        "-pix_fmt",
        "rgba",
        "-f",
        "rawvideo",
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",  # Changed from "ultrafast" to "veryfast" for a better balance of speed and quality
        "-tune",
        "fastdecode",  # Added tune option for faster decoding
        "-crf",
        "23",  # CRF value, kept at 23 for a balance of speed and quality
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
        "-movflags",
        "+faststart",  # Optimize for web playback
        "-threads",
        "16",  # Use all available CPU threads
        output_filepath,
    )
    p = subprocess.Popen(cmdstring, stdin=subprocess.PIPE)

    im = ax.imshow(memory, interpolation="none", aspect="auto", animated=True)
    ax.set_xlabel("Pages")
    ax.set_ylabel("Blocks")
    ax.set_xticks(np.arange(-0.5, memory.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, memory.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=0.125)

    total_frames = len(operation_entries) // frame_step
    frame_times = []

    batch_memory_updates = []

    for i in range(0, len(operation_entries), frame_step):
        frame_start_time = time.time()

        batch_memory_updates.clear()

        for j in range(i, min(i + frame_step, len(operation_entries))):
            operation = operation_entries[j]
            update_memory(memory, operation, metadata, operation.operation, operation_tracker)
            batch_memory_updates.append(np.copy(memory))

        # Now, draw all batch updates at once
        for memory_snapshot in batch_memory_updates:
            im.set_array(memory_snapshot)
            ax.set_title(f"Frame: {i // frame_step + 1} / {total_frames}")
            fig.canvas.draw()
            string = fig.canvas.buffer_rgba()
            p.stdin.write(string)

        frame_end_time = time.time()
        frame_time = frame_end_time - frame_start_time
        frame_times.append(frame_time)

        print(f"Processing frame {i // frame_step + 1} / {total_frames} | Time: {frame_time:.4f}s", end="\r")

    p.stdin.close()
    p.wait()
    plt.close(fig)

    end_time = time.time()
    total_time = end_time - start_time
    avg_frame_time = sum(frame_times) / len(frame_times)
    fps = 1 / avg_frame_time

    print("\nVideo creation completed.")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Total frames: {total_frames}")
    print(f"Average time per frame: {avg_frame_time:.4f} seconds")
    print(f"Frames per second: {fps:.2f}")
    print(f"Total samples processed: {len(operation_entries)}")
    print(f"Samples per frame: {frame_step}")


if __name__ == "__main__":
    file_path = f"db/observability/memory/{channel}.json"
    observability_info = load_observability_data(file_path)
    output_file_path = f"tools/out/{channel}.mp4"
    create_erase_heatmap_movie(observability_info, output_file_path, frame_step=32)
