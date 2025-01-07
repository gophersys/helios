import os
import yaml
import argparse


# Function to load the contents of an api.yaml file
def load_yaml_file(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


# Function to recursively find all api.yaml files
def find_api_files(directory):
    api_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == "api.yaml":
                api_files.append(os.path.join(root, file))
    return api_files


# Function to combine all api.yaml files into one OpenAPI file
def combine_api_files(api_files):
    combined_paths = {}

    for api_file in api_files:
        try:
            api_data = load_yaml_file(api_file)
            combined_paths.update(api_data)  # Add the paths to the combined paths
        except yaml.YAMLError as exc:
            print(f"Error parsing {api_file}: {exc}")

    return combined_paths


# Function to create the final openapi.yaml file
def create_openapi_yaml(combined_paths, output_file):
    openapi_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Concord Proxy API",
            "description": "The concord proxy server is the interface to the test backend system",
            "version": "1.0.0",
        },
        "servers": [{"url": "http://127.0.0.1:7600", "description": "Local development server"}],
        "paths": combined_paths,  # Insert the combined paths
    }

    with open(output_file, "w") as file:
        yaml.dump(openapi_spec, file, sort_keys=False)

    print(f"OpenAPI spec generated at {output_file}")


# Main function to run the script
def main():
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec by combining all api.yaml files.")
    parser.add_argument("directory", type=str, help="Directory to search for api.yaml files.")
    parser.add_argument("-o", "--output", type=str, default="openapi.yaml", help="Output OpenAPI file path.")

    args = parser.parse_args()

    # Find all api.yaml files
    api_files = find_api_files(args.directory)
    if not api_files:
        print("No api.yaml files found.")
        return

    # Combine all api.yaml files
    combined_paths = combine_api_files(api_files)

    # Create the final OpenAPI spec
    create_openapi_yaml(combined_paths, args.output)


if __name__ == "__main__":
    main()
