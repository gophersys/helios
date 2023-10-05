cmake_minimum_required(VERSION 3.20.0)

# Private includes
zephyr_include_directories(include)

# Add source files (assuming each subdirectory has its own CMakeLists.txt)
add_subdirectory(rpc)