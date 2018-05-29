cmake_minimum_required(VERSION 3.3)
project(CCShellExtContextMenuHandler)
add_definitions(/D "WIN32" /D "NDEBUG" /D "_WINDOWS" /D "_USRDLL" /D "CPPSHELLEXTCONTEXTMENUHANDLER_EXPORTS" /D "_WINDLL" /D "_UNICODE" /D "UNICODE")

set(SOURCE_FILES
    src/CCShellExtContextMenuHandler/cpp/utils/ClassFactory.h
    src/CCShellExtContextMenuHandler/cpp/dllmain.cpp
    src/CCShellExtContextMenuHandler/cpp/ctxmenu/FileContextMenuExt.cpp
    src/CCShellExtContextMenuHandler/cpp/ctxmenu/FileContextMenuExt.h
	src/CCShellExtContextMenuHandler/cpp/overlay/OverlaySyncedExt.h
	src/CCShellExtContextMenuHandler/cpp/overlay/OverlaySyncedExt.cpp
	src/CCShellExtContextMenuHandler/cpp/overlay/OverlayUnSyncedExt.h
	src/CCShellExtContextMenuHandler/cpp/overlay/OverlayUnSyncedExt.cpp
    src/CCShellExtContextMenuHandler/cpp/Reg.cpp
    src/CCShellExtContextMenuHandler/cpp/Reg.h
    src/CCShellExtContextMenuHandler/cpp/utils/utils.cpp
	src/CCShellExtContextMenuHandler/cpp/utils/logging.cpp
	src/CCShellExtContextMenuHandler/cpp/utils/logging.h
	src/CCShellExtContextMenuHandler/cpp/utils/utils.h
	src/CCShellExtContextMenuHandler/cpp/Ipc.h
	src/CCShellExtContextMenuHandler/cpp/Ipc.cpp
	src/CCShellExtContextMenuHandler/cpp/config.h
	src/CCShellExtContextMenuHandler/resources/Resource.rc
  ${THRIFT_GENERATED}
    )

link_directories(C:/local/boost_1_60_0/lib64-msvc-12.0)

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/src/CCShellExtContextMenuHandler/cpp)

add_library(CCShellExtContextMenuHandler MODULE ${SOURCE_FILES} )
add_executable (Tests  ${SOURCE_FILES} ${CMAKE_CURRENT_SOURCE_DIR}/src/CCShellExtContextMenuHandler/cpp/tests.cpp)
target_link_libraries(Tests gdiplus Shlwapi)

target_link_libraries(CCShellExtContextMenuHandler gdiplus Shlwapi)

set(CMAKE_MODULE_LINKER_FLAGS
      "/DEF:${CMAKE_CURRENT_SOURCE_DIR}/GlobalExportFunctions.def")

# kill explorer before linking
# add_custom_command(TARGET ${PROJECT_NAME}
#    PRE_LINK
#    COMMAND taskkill /f /im explorer.exe
# )


# kill explorer before linking
# add_custom_command(TARGET ${PROJECT_NAME}
#    POST_BUILD
#    COMMAND "explorer"
# )