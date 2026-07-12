cmake_minimum_required(VERSION 3.22.1)
project(zeecut C)

add_executable(arp_spoof
    arp_spoof.c
)

target_link_libraries(arp_spoof)

set_target_properties(arp_spoof PROPERTIES
    OUTPUT_NAME "libarp_spoof"
    SUFFIX ".so"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
)
