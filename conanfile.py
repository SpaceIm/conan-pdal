from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
import os

required_conan_version = ">=1.33.0"


class PdalConan(ConanFile):
    name = "pdal"
    description = "PDAL is Point Data Abstraction Library. GDAL for point cloud data."
    license = "BSD-3-Clause"
    topics = ("conan", "pdal", "gdal")
    homepage = "https://pdal.io"
    url = "https://github.com/conan-io/conan-center-index"

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_unwind": [True, False],
        "with_xml": [True, False],
        "with_zstd": [True, False],
        "with_laszip": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_unwind": False,
        "with_xml": True,
        "with_zstd": True,
        "with_laszip": True,
    }

    exports_sources = ["CMakeLists.txt", "patches/*"]
    generators = "cmake", "cmake_find_package"
    _cmake = None

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        if self.settings.os not in ["Linux", "FreeBSD"]:
            del self.options.with_unwind

    def configure(self):
        if self.options.shared:
            del self.options.fPIC
        if self.settings.compiler.cppstd:
            tools.check_min_cppstd(self, 11)
        if self.settings.compiler == "gcc" and tools.Version(self.settings.compiler.version) < 5:
            raise ConanInvalidConfiguration ("This compiler version is unsupported")

    def requirements(self):
        # TODO package improvements:
        # - switch from vendored arbiter (not in CCI). disabled openssl and curl are deps of arbiter
        # - switch from vendor/nlohmann to nlohmann_json (in CCI)
        self.requires("boost/1.76.0")
        self.requires("eigen/3.3.9")
        self.requires("gdal/3.2.1")
        self.requires("libgeotiff/1.6.0")
        self.requires("nanoflann/1.3.2")
        if self.options.with_xml:
            self.requires("libxml2/2.9.10")
        if self.options.with_zstd:
            self.requires("zstd/1.5.0")
        if self.options.with_laszip:
            self.requires("laszip/3.4.3")
        if self.options.get_safe("with_unwind"):
            self.requires("libunwind/1.5.0")

    @property
    def _required_boost_components(self):
        return ["filesystem"]

    def validate(self):
        miss_boost_required_comp = any(getattr(self.options["boost"], "without_{}".format(boost_comp), True) for boost_comp in self._required_boost_components)
        if self.options["boost"].header_only or miss_boost_required_comp:
            raise ConanInvalidConfiguration("{0} requires non header-only boost with these components: {1}".format(self.name, ", ".join(self._required_boost_components)))

    def source(self):
        tools.get(**self.conan_data["sources"][self.version],
                  destination=self._source_subfolder, strip_root=True)

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)
        self._cmake.definitions["PDAL_BUILD_STATIC"] = not self.options.shared
        self._cmake.definitions["WITH_TESTS"] = False
        self._cmake.definitions["WITH_LAZPERF"] = False
        self._cmake.definitions["WITH_LASZIP"] = self.options.with_laszip
        self._cmake.definitions["WITH_STATIC_LASZIP"] = True # doesn't really matter but avoid to inject useless definition
        self._cmake.definitions["WITH_ZSTD"] = self.options.with_zstd
        self._cmake.definitions["WITH_ZLIB"] = True
        # disable plugin that requires postgresql
        self._cmake.definitions["BUILD_PLUGIN_PGPOINTCLOUD"] = False
        self._cmake.configure()
        return self._cmake

    def _patch_sources(self):
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            tools.patch(**patch)
        # drop conflicting CMake files
        # LASzip works fine
        for module in ('ZSTD', 'ICONV', 'GeoTIFF', 'Curl'):
            os.remove(os.path.join(self._source_subfolder, "cmake", "modules", "Find"+module+".cmake"))
        # disabling libxml2 support is only done via patching
        if not self.options.with_xml:
            tools.replace_in_file(
                os.path.join(self._source_subfolder, "CMakeLists.txt"),
                "include(${PDAL_CMAKE_DIR}/libxml2.cmake)",
                "#include(${PDAL_CMAKE_DIR}/libxml2.cmake)")
        # remove vendored eigen
        tools.rmdir(os.path.join(self._source_subfolder, 'vendor', 'eigen'))
        # remove vendored nanoflann. include path is patched
        tools.rmdir(os.path.join(self._source_subfolder, 'vendor', 'nanoflann'))
        # remove vendored boost
        tools.rmdir(os.path.join(self._source_subfolder, "vendor", "pdalboost"))
        tools.replace_in_file(os.path.join(self._source_subfolder, "CMakeLists.txt"),
                              "add_subdirectory(vendor/pdalboost)",
                              "")
        tools.replace_in_file(os.path.join(self._source_subfolder, "pdal", "util", "CMakeLists.txt"),
                              "${PDAL_BOOST_LIB_NAME}", "${CONAN_LIBS}")
        tools.replace_in_file(os.path.join(self._source_subfolder, "pdal", "util", "FileUtils.cpp"),
                              "pdalboost::", "boost::")
        # No rpath manipulation
        tools.replace_in_file(os.path.join(self._source_subfolder, "CMakeLists.txt"),
                              "include(${PDAL_CMAKE_DIR}/rpath.cmake)",
                              "")
        # No reexport
        tools.replace_in_file(os.path.join(self._source_subfolder, "CMakeLists.txt"),
                              "set(PDAL_REEXPORT \"-Wl,-reexport_library,$<TARGET_FILE:${PDAL_UTIL_LIB_NAME}>\")",
                              "")
        # fix static build
        if not self.options.shared:
            tools.replace_in_file(os.path.join(self._source_subfolder, "CMakeLists.txt"),
                                  "add_definitions(\"-DPDAL_DLL_EXPORT=1\")",
                                  "")
            tools.replace_in_file(os.path.join(self._source_subfolder, "CMakeLists.txt"),
                                  "${PDAL_BASE_LIB_NAME} ${PDAL_UTIL_LIB_NAME}",
                                  "${PDAL_BASE_LIB_NAME} ${PDAL_UTIL_LIB_NAME} ${PDAL_ARBITER_LIB_NAME} ${PDAL_KAZHDAN_LIB_NAME}")
            tools.replace_in_file(os.path.join(self._source_subfolder, "cmake", "macros.cmake"),
                                  "        install(TARGETS ${_name}",
                                  "    endif()\n    if (PDAL_LIB_TYPE STREQUAL \"STATIC\" OR NOT ${_library_type} STREQUAL \"STATIC\")\n         install(TARGETS ${_name}")
            tools.replace_in_file(os.path.join(self._source_subfolder, "pdal", "util", "CMakeLists.txt"),
                                  "PDAL_ADD_FREE_LIBRARY(${PDAL_UTIL_LIB_NAME} SHARED ${PDAL_UTIL_SOURCES})",
                                  "PDAL_ADD_FREE_LIBRARY(${PDAL_UTIL_LIB_NAME} ${PDAL_LIB_TYPE} ${PDAL_UTIL_SOURCES})")

    def build(self):
        self._patch_sources()
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        self.copy("Copyright.txt", dst="licenses", src=self._source_subfolder)
        cmake = self._configure_cmake()
        cmake.install()

    def package(self):
        self.copy("LICENSE.txt", src=self._source_subfolder, dst="licenses", ignore_case=True, keep_path=False)
        cmake = self._configure_cmake()
        cmake.install()
        tools.rmdir(os.path.join(self.package_folder, 'lib', 'cmake'))
        tools.rmdir(os.path.join(self.package_folder, 'lib', 'pkgconfig'))
        tools.remove_files_by_mask(os.path.join(self.package_folder, "bin"), "pdal-config*")

    def package_info(self):
        self.cpp_info.names["cmake_find_package"] = "PDAL"
        self.cpp_info.names["cmake_find_package_multi"] = "PDAL"
        self.cpp_info.names["pkg_config"] = "pdal"
        pdal_base_name = "pdalcpp" if self.settings.os == "Windows" or tools.is_apple_os(self.settings.os) else "pdal_base"
        self.cpp_info.libs = [pdal_base_name, "pdal_util"]
        if not self.options.shared:
            self.cpp_info.libs.extend(["pdal_arbiter", "pdal_kazhdan"])
        if self.settings.os == "Linux":
            self.cpp_info.system_libs.extend(["dl", "m"])
