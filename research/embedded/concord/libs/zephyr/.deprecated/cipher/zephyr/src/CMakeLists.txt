cmake_minimum_required(VERSION 3.20.0)

# Private includes
zephyr_include_directories(include)

# Add source files (assuming each subdirectory has its own CMakeLists.txt)
add_subdirectory(daemon)
add_subdirectory(event)
add_subdirectory(interface)
add_subdirectory(registry)
add_subdirectory(rpc)
add_subdirectory(serdes)
add_subdirectory(services)
add_subdirectory(stream)