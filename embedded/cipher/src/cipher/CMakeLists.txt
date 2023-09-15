cmake_minimum_required(VERSION 3.20.0)

# Include directories
zephyr_include_directories(include) # private

# Add source files (assuming each subdirectory has its own CMakeLists.txt)
add_subdirectory(tal)
add_subdirectory(protocol)