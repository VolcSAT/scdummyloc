# sceewlog
SET(MAIN_PY scdummyloc.py)
SET(EEWLOG_TARGET scdummyloc)
SET(EEWLOG_FILES scdummyloc.py)

SC_ADD_PYTHON_EXECUTABLE(DUMLOC)


IF(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../../../trunk/apps/templates/initd.py")
  SC_INSTALL_INIT(${DUMLOC_TARGET} ../../../trunk/apps/templates/initd.py)
ELSE()
  SC_INSTALL_INIT(${DUMLOC_TARGET} ../../../../base/common/apps/templates/initd.py)
ENDIF()


FILE(GLOB descs "${CMAKE_CURRENT_SOURCE_DIR}/descriptions/*.xml")
INSTALL(FILES ${descs} DESTINATION ${SC3_PACKAGE_APP_DESC_DIR})