cmake_minimum_required(VERSION 3.15)
project(hft_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(hft_core MODULE
    src/order_book.cpp
    python/bindings.cpp
)

target_include_directories(hft_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
