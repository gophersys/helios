cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr)

project(dns-sec)

#add_subdirectory(src/dnssec)
add_subdirectory(src/dns_sec)
target_sources(app PRIVATE src/main.c)