cmake_minimum_required(VERSION 3.1)
project(test_package)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS)

# keep close to the upstream example docs
find_package(PDAL 2.0.0 REQUIRED)

add_executable(${PROJECT_NAME} test_package.cpp)
target_include_directories(${PROJECT_NAME} PRIVATE ${PDAL_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME} ${PDAL_LIBRARIES})
set_property(TARGET ${PROJECT_NAME} PROPERTY CXX_STANDARD 11)
