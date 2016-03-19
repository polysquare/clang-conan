from contextlib import contextmanager
from conans import ConanFile, CMake
from conans.tools import download, unzip
import shutil
import os
import platform

VERSION = "3.8.0"


@contextmanager
def in_dir(directory):
    last_dir = os.getcwd()
    try:
        os.makedirs(directory)
    except OSError:
        pass

    try:
        os.chdir(directory)
        yield directory
    finally:
        os.chdir(last_dir)


def extract_from_url(url):
    print("download {}".format(url))
    zip_name = os.path.basename(url)
    download(url, zip_name)
    unzip(zip_name)
    os.unlink(zip_name)


def download_extract_llvm_component(component, release, extract_to):
    extract_from_url("https://bintray.com/artifact/download/"
                     "polysquare/LLVM/{comp}-{ver}.src.zip"
                     "".format(ver=release, comp=component))
    shutil.move("{comp}-{ver}.src".format(comp=component,
                                          ver=release),
                extract_to)


BUILD_DIR = ("C:/__build" if platform.system == "Windows"
             else "build")
INSTALL_DIR = "install"  # This needs to be a relative path

class ClangConan(ConanFile):
    name = "clang"
    version = os.environ.get("CONAN_VERSION_OVERRIDE", VERSION)
    generators = "cmake"
    requires = ("llvm/3.8.0@smspillaz/stable", )
    url = "http://github.com/smspillaz/clang-conan"
    license = "BSD"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = "shared=True"

    def config(self):
        try:  # Try catch can be removed when conan 0.8 is released
            del self.settings.compiler.libcxx
        except:
            pass

    def source(self):
        download_extract_llvm_component("cfe", ClangConan.version,
                                        "clang")
        download_extract_llvm_component("compiler-rt", ClangConan.version,
                                        "compiler-rt")
        download_extract_llvm_component("libcxx", ClangConan.version,
                                        "libcxx")
        download_extract_llvm_component("clang-tools-extra", ClangConan.version,
                                        "clang/tools/extra")

    def build(self):
        cmake = CMake(self.settings)

        for component in ["clang", "compiler-rt", "libcxx"]:
            build = os.path.join(BUILD_DIR, component)
            install = os.path.join(INSTALL_DIR, component)
            try:
                os.makedirs(install)
            except OSError:
                pass

            if not os.path.exists(os.path.join(self.conanfile_directory,
                                               component,
                                               "CMakeListsOriginal.txt")):
                shutil.move(os.path.join(self.conanfile_directory,
                                         component,
                                         "CMakeLists.txt"),
                            os.path.join(self.conanfile_directory,
                                         component,
                                         "CMakeListsOriginal"))
                with open(os.path.join(self.conanfile_directory,
                                       component,
                                       "CMakeLists.txt"), "w") as cmakelists_file:
                    cmakelists_file.write("cmake_minimum_required(VERSION 2.8)\n"
                                          "include(\"${CMAKE_CURRENT_LIST_DIR}/../conanbuildinfo.cmake\")\n"
                                          "conan_basic_setup()\n"
                                          "set (CMAKE_PREFIX_PATH \"${CONAN_LLVM_ROOT}\")\n"
                                          "set (CMAKE_PROGRAM_PATH \"${CONAN_BIN_DIRS_LLVM}\")\n"
                                          "if (APPLE OR UNIX)\n"
                                          "  set (CMAKE_EXE_LINKER_FLAGS \"${CMAKE_EXE_LINKER_FLAGS} -Wl,-rpath,${CONAN_LIB_DIRS}\")\n"
                                          "  set (CMAKE_SHARED_LINKER_FLAGS \"${CMAKE_SHARED_LINKER_FLAGS} -Wl,-rpath,${CONAN_LIB_DIRS}\")\n"
                                          "endif ()\n"
                                          "message (STATUS \"${CMAKE_PROGRAM_PATH}\")\n"
                                          "include(CMakeListsOriginal)\n")

            try:
                shutil.rmtree(build)
            except OSError:
                pass

            with in_dir(build):
                self.run("cmake \"%s\" %s"
                         " -DCLANG_INCLUDE_DOCS=OFF"
                         " -DCLANG_INCLUDE_TESTS=OFF"
                         " -DCLANG_TOOLS_INCLUDE_EXTRA_DOCS=OFF"
                         " -DCOMPILER_RT_INCLUDE_TESTS=OFF"
                         " -DLIBCXX_INCLUDE_TESTS=OFF"
                         " -DLIBCXX_INCLUDE_DOCS=OFF"
                         " -DLLVM_INCLUDE_TESTS=OFF"
                         " -DLLVM_INCLUDE_EXAMPLES=OFF"
                         " -DLLVM_INCLUDE_GO_TESTS=OFF"
                         " -DLLVM_BUILD_TESTS=OFF"
                         " -DLIBCXXABI_LIBCXX_INCLUDES=\"%s/libcxx/include\""
                         " -DCMAKE_VERBOSE_MAKEFILE=1"
                         " -DLLVM_TARGETS_TO_BUILD=X86"
                         " -DCMAKE_INSTALL_PREFIX=\"%s\""
                         " -DBUILD_SHARED_LIBS=%s"
                         "" % (os.path.join(self.conanfile_directory,
                                            component),
                               cmake.command_line,
                               os.path.abspath(os.path.join(build, "..")),
                               os.path.join(self.conanfile_directory,
                                            install),
                               ("ON" if self.options.shared else "OFF")))
                self.run("cmake --build . {cfg} -- {j}"
                         "".format(cfg=cmake.build_config,
                                   j=("-j4" if platform.system() != "Windows"
                                      else "")))
                self.run("cmake --build . -- install")

    def package(self):
        for component in ["clang", "compiler-rt", "libcxx"]:
            install = os.path.join(INSTALL_DIR, component)
            self.copy(pattern="*",
                      dst="include",
                      src=os.path.join(install, "include"),
                      keep_path=True)
            for pattern in ["*.a", "*.h", "*.so", "*.lib", "*.dylib", "*.dll", "*.cmake"]:
                self.copy(pattern=pattern,
                          dst="lib",
                          src=os.path.join(install, "lib"),
                          keep_path=True)
            self.copy(pattern="*",
                      dst="share",
                      src=os.path.join(install, "share"),
                      keep_path=True)
            self.copy(pattern="*",
                      dst="bin",
                      src=os.path.join(install, "bin"),
                      keep_path=True)
            self.copy(pattern="*",
                      dst="libexec",
                      src=os.path.join(install, "libexec"),
                      keep_path=True)

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")
