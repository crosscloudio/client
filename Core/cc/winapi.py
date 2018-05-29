"""
constants and function definitions from winapi
"""

# pylint: disable=invalid-name,missing-docstring

import ctypes
import ctypes.wintypes

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.wintypes.DWORD),
                ("dwHighDateTime", ctypes.wintypes.DWORD)]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [('dwFileAttributes', ctypes.wintypes.DWORD),
                ('ftCreationTime', FILETIME),
                ('ftLastAccessTime', FILETIME),
                ('ftLastWriteTime', FILETIME),
                ('dwVolumeSerialNumber', ctypes.wintypes.DWORD),
                ('nFileSizeHigh', ctypes.wintypes.DWORD),
                ('nFileSizeLow', ctypes.wintypes.DWORD),
                ('nNumberOfLinks', ctypes.wintypes.DWORD),
                ('nFileIndexHigh', ctypes.wintypes.DWORD),
                ('nFileIndexLow', ctypes.wintypes.DWORD)]


# typedef struct _NETRESOURCE {
#   DWORD  dwScope;
#   DWORD  dwType;
#   DWORD  dwDisplayType;
#   DWORD  dwUsage;
#   LPTSTR lpLocalName;
#   LPTSTR lpRemoteName;
#   LPTSTR lpComment;
#   LPTSTR lpProvider;
# } NETRESOURCE;
class NETRESOURCE(ctypes.Structure):
    _fields_ = [('dwScope', ctypes.wintypes.DWORD),
                ('dwType', ctypes.wintypes.DWORD),
                ('dwDisplayType', ctypes.wintypes.DWORD),
                ('dwUsage', ctypes.wintypes.DWORD),
                ('lpLocalName', ctypes.wintypes.LPWSTR),
                ('lpRemoteName', ctypes.wintypes.LPWSTR),
                ('lpComment', ctypes.wintypes.LPWSTR),
                ('lpProvider', ctypes.wintypes.LPWSTR)]


LPNETRESOURCE = ctypes.POINTER(NETRESOURCE)

CreateFile = ctypes.windll.kernel32.CreateFileW
CreateFile.restype = ctypes.wintypes.HANDLE
CreateFile.argtypes = (
    ctypes.c_wchar_p,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
)

GetFileInformationByHandle = ctypes.windll.kernel32.GetFileInformationByHandle
GetFileInformationByHandle.restype = ctypes.wintypes.BOOL
GetFileInformationByHandle.argtypes = (
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
)

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.restype = ctypes.wintypes.BOOL
CloseHandle.argtypes = (ctypes.wintypes.HANDLE,)

FILE_NOTIFY_CHANGE_FILE_NAME = 0x01
FILE_NOTIFY_CHANGE_DIR_NAME = 0x02
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x04
FILE_NOTIFY_CHANGE_SIZE = 0x08
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x010
FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x020
FILE_NOTIFY_CHANGE_CREATION = 0x040
FILE_NOTIFY_CHANGE_SECURITY = 0x0100

FILE_LIST_DIRECTORY = 0x01
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
FILE_SHARE_DELETE = 0x04
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OVERLAPPED = 0x40000000
FILE_READ_ATTRIBUTES = 0x80
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_ATTRIBUTE_READONLY = 0x1
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000

THREAD_TERMINATE = 0x0001

FILE_ACTION_ADDED = 1
FILE_ACTION_REMOVED = 2
FILE_ACTION_MODIFIED = 3
FILE_ACTION_RENAMED_OLD_NAME = 4
FILE_ACTION_RENAMED_NEW_NAME = 5
FILE_ACTION_OVERFLOW = 0xFFFF

WAIT_ABANDONED = 0x00000080
WAIT_IO_COMPLETION = 0x000000C0
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

NO_ERROR = 0


def _errcheck_bool(value, _, args):
    if not value:
        raise ctypes.WinError()
    return args


def _errcheck_handle(value, _, args):
    if not value:
        raise ctypes.WinError()
    if value == INVALID_HANDLE_VALUE:
        raise ctypes.WinError()
    return args


def _errcheck_dword(value, _, args):
    if value == 0xFFFFFFFF:
        raise ctypes.WinError()
    return args


def _errcheck_fail_zero(value, _, args):
    """ checks if the value is zero and fails then"""
    if value == 0:
        raise ctypes.WinError()
    return args


def _errcheck_winnet(value, _, args):
    if value != NO_ERROR:
        raise ctypes.WinError(value)
    return args


class OVERLAPPED(ctypes.Structure):
    _fields_ = [('Internal', ctypes.wintypes.LPVOID),
                ('InternalHigh', ctypes.wintypes.LPVOID),
                ('Offset', ctypes.wintypes.DWORD),
                ('OffsetHigh', ctypes.wintypes.DWORD),
                ('Pointer', ctypes.wintypes.LPVOID),
                ('hEvent', ctypes.wintypes.HANDLE)]


LPOVERLAPPED = ctypes.POINTER(OVERLAPPED)

try:
    ReadDirectoryChangesW = ctypes.windll.kernel32.ReadDirectoryChangesW
except AttributeError:
    raise ImportError("ReadDirectoryChangesW is not available")

ReadDirectoryChangesW.restype = ctypes.wintypes.BOOL
ReadDirectoryChangesW.errcheck = _errcheck_bool
ReadDirectoryChangesW.argtypes = (
    ctypes.wintypes.HANDLE,  # hDirectory
    ctypes.wintypes.LPVOID,  # lpBuffer
    ctypes.wintypes.DWORD,  # nBufferLength
    ctypes.wintypes.BOOL,  # bWatchSubtree
    ctypes.wintypes.DWORD,  # dwNotifyFilter
    ctypes.POINTER(ctypes.wintypes.DWORD),  # lpBytesReturned
    ctypes.POINTER(OVERLAPPED),  # lpOverlapped
    ctypes.wintypes.LPVOID  # FileIOCompletionRoutine # lpCompletionRoutine
)

CreateFileW = ctypes.windll.kernel32.CreateFileW
CreateFileW.restype = ctypes.wintypes.HANDLE
CreateFileW.errcheck = _errcheck_handle
CreateFileW.argtypes = (
    ctypes.wintypes.LPCWSTR,  # lpFileName
    ctypes.wintypes.DWORD,  # dwDesiredAccess
    ctypes.wintypes.DWORD,  # dwShareMode
    ctypes.wintypes.LPVOID,  # lpSecurityAttributes
    ctypes.wintypes.DWORD,  # dwCreationDisposition
    ctypes.wintypes.DWORD,  # dwFlagsAndAttributes
    ctypes.wintypes.HANDLE  # hTemplateFile
)

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.errcheck = _errcheck_bool
CloseHandle.restype = ctypes.wintypes.BOOL
CloseHandle.argtypes = (
    ctypes.wintypes.HANDLE,  # hObject
)

CreateEvent = ctypes.windll.kernel32.CreateEventW
CreateEvent.restype = ctypes.wintypes.HANDLE
CreateEvent.errcheck = _errcheck_handle
CreateEvent.argtypes = (
    ctypes.wintypes.LPVOID,  # lpEventAttributes
    ctypes.wintypes.BOOL,  # bManualReset
    ctypes.wintypes.BOOL,  # bInitialState
    ctypes.wintypes.LPCWSTR,  # lpName
)

# BOOL WINAPI ReadFile(
#   _In_        HANDLE       hFile,
#   _Out_       LPVOID       lpBuffer,
#   _In_        DWORD        nNumberOfBytesToRead,
#   _Out_opt_   LPDWORD      lpNumberOfBytesRead,
#   _Inout_opt_ LPOVERLAPPED lpOverlapped
# );
ReadFile = ctypes.windll.kernel32.ReadFile
ReadFile.restype = ctypes.wintypes.BOOL
ReadFile.errcheck = _errcheck_bool
ReadFile.argtypes = (
    ctypes.wintypes.HANDLE,  # hFile
    ctypes.wintypes.LPVOID,  # lpBuffer
    ctypes.wintypes.DWORD,  # nNumberOfBytesToRead
    ctypes.wintypes.LPDWORD,  # lpNumberOfBytesRead
    LPOVERLAPPED,  # lpOverlapped
)

# DWORD WINAPI GetLongPathName(
#   _In_  LPCTSTR lpszShortPath,
#   _Out_ LPTSTR  lpszLongPath,
#   _In_  DWORD   cchBuffer
# );

GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
GetLongPathName.restype = ctypes.wintypes.DWORD
GetLongPathName.errcheck = _errcheck_fail_zero
GetLongPathName.argtypes = (
    ctypes.wintypes.LPCWSTR,  # lpszShortPath
    ctypes.wintypes.LPWSTR,  # lpszLongPath
    ctypes.wintypes.DWORD  # nNumberOfBytesToRead
)

# BOOL WINAPI SetFileAttributes(
#   _In_ LPCTSTR lpFileName,
#   _In_ DWORD   dwFileAttributes
# );
SetFileAttributes = ctypes.windll.kernel32.SetFileAttributesW
SetFileAttributes.restype = ctypes.wintypes.BOOL
SetFileAttributes.errcheck = _errcheck_bool
SetFileAttributes.argtypes = (
    ctypes.wintypes.LPCWSTR,  # lpFileName
    ctypes.wintypes.DWORD,  # dwFileAttributes
)

# BOOL WINAPI GetDiskFreeSpaceEx(
#   _In_opt_  LPCTSTR         lpDirectoryName,
#   _Out_opt_ PULARGE_INTEGER lpFreeBytesAvailable,
#   _Out_opt_ PULARGE_INTEGER lpTotalNumberOfBytes,
#   _Out_opt_ PULARGE_INTEGER lpTotalNumberOfFreeBytes
# );
GetDiskFreeSpaceEx = ctypes.windll.kernel32.GetDiskFreeSpaceExW
GetDiskFreeSpaceEx.restype = ctypes.wintypes.BOOL
GetDiskFreeSpaceEx.errcheck = _errcheck_bool
GetDiskFreeSpaceEx.argtypes = (
    ctypes.wintypes.LPCWSTR,  # lpDirectoryName
    ctypes.wintypes.PULARGE_INTEGER,  # lpFreeBytesAvailable
    ctypes.wintypes.PULARGE_INTEGER,  # lpTotalNumberOfBytes
    ctypes.wintypes.PULARGE_INTEGER,  # lpTotalNumberOfFreeBytes
)

# DWORD WNetAddConnection2(
#   _In_ LPNETRESOURCE lpNetResource,
#   _In_ LPCTSTR       lpPassword,
#   _In_ LPCTSTR       lpUsername,
#   _In_ DWORD         dwFlags
# );
WNetAddConnection2 = ctypes.windll.mpr.WNetAddConnection2W
WNetAddConnection2.restype = ctypes.wintypes.DWORD
WNetAddConnection2.errcheck = _errcheck_winnet
WNetAddConnection2.argtypes = (
    LPNETRESOURCE,  # lpDirectoryName
    ctypes.wintypes.LPCWSTR,  # lpFreeBytesAvailable
    ctypes.wintypes.LPCWSTR,  # lpTotalNumberOfBytes
    ctypes.wintypes.DWORD,  # lpTotalNumberOfFreeBytes
)

SetEvent = ctypes.windll.kernel32.SetEvent
SetEvent.restype = ctypes.wintypes.BOOL
SetEvent.errcheck = _errcheck_bool
SetEvent.argtypes = (
    ctypes.wintypes.HANDLE,  # hEvent
)

WaitForSingleObjectEx = ctypes.windll.kernel32.WaitForSingleObjectEx
WaitForSingleObjectEx.restype = ctypes.wintypes.DWORD
WaitForSingleObjectEx.errcheck = _errcheck_dword
WaitForSingleObjectEx.argtypes = (
    ctypes.wintypes.HANDLE,  # hObject
    ctypes.wintypes.DWORD,  # dwMilliseconds
    ctypes.wintypes.BOOL,  # bAlertable
)

CreateIoCompletionPort = ctypes.windll.kernel32.CreateIoCompletionPort
CreateIoCompletionPort.restype = ctypes.wintypes.HANDLE
CreateIoCompletionPort.errcheck = _errcheck_handle
CreateIoCompletionPort.argtypes = (
    ctypes.wintypes.HANDLE,  # FileHandle
    ctypes.wintypes.HANDLE,  # ExistingCompletionPort
    ctypes.wintypes.LPVOID,  # CompletionKey
    ctypes.wintypes.DWORD,  # NumberOfConcurrentThreads
)

GetQueuedCompletionStatus = ctypes.windll.kernel32.GetQueuedCompletionStatus
GetQueuedCompletionStatus.restype = ctypes.wintypes.BOOL
GetQueuedCompletionStatus.errcheck = _errcheck_bool
GetQueuedCompletionStatus.argtypes = (
    ctypes.wintypes.HANDLE,  # CompletionPort
    ctypes.wintypes.LPVOID,  # lpNumberOfBytesTransferred
    ctypes.wintypes.LPVOID,  # lpCompletionKey
    ctypes.POINTER(OVERLAPPED),  # lpOverlapped
    ctypes.wintypes.DWORD,  # dwMilliseconds
)

PostQueuedCompletionStatus = ctypes.windll.kernel32.PostQueuedCompletionStatus
PostQueuedCompletionStatus.restype = ctypes.wintypes.BOOL
PostQueuedCompletionStatus.errcheck = _errcheck_bool
PostQueuedCompletionStatus.argtypes = (
    ctypes.wintypes.HANDLE,  # CompletionPort
    ctypes.wintypes.DWORD,  # lpNumberOfBytesTransferred
    ctypes.wintypes.DWORD,  # lpCompletionKey
    ctypes.POINTER(OVERLAPPED),  # lpOverlapped
)

# void SHChangeNotify(
#            LONG    wEventId,
#            UINT    uFlags,
#   _In_opt_ LPCVOID dwItem1,
#   _In_opt_ LPCVOID dwItem2
# );
SHChangeNotify = ctypes.windll.shell32.SHChangeNotify
SHChangeNotify.restype = None
SHChangeNotify.argtypes = (
    ctypes.wintypes.LONG,  # wEventId
    ctypes.wintypes.UINT,  # uFlags
    ctypes.wintypes.LPCVOID,  # dwItem1
    ctypes.wintypes.LPCVOID  # dwItem2
)
SHCNRF_InterruptLevel = 0x0001
SHCNRF_ShellLevel = 0x0002
SHCNRF_RecursiveInterrupt = 0x1000
SHCNRF_NewDelivery = 0x8000

SHCNE_RENAMEITEM = 0x00000001
SHCNE_CREATE = 0x00000002
SHCNE_DELETE = 0x00000004
SHCNE_MKDIR = 0x00000008
SHCNE_RMDIR = 0x00000010
SHCNE_MEDIAINSERTED = 0x00000020
SHCNE_MEDIAREMOVED = 0x00000040
SHCNE_DRIVEREMOVED = 0x00000080
SHCNE_DRIVEADD = 0x00000100
SHCNE_NETSHARE = 0x00000200
SHCNE_NETUNSHARE = 0x00000400
SHCNE_ATTRIBUTES = 0x00000800
SHCNE_UPDATEDIR = 0x00001000
SHCNE_UPDATEITEM = 0x00002000
SHCNE_SERVERDISCONNECT = 0x00004000
SHCNE_UPDATEIMAGE = 0x00008000
SHCNE_DRIVEADDGUI = 0x00010000
SHCNE_RENAMEFOLDER = 0x00020000
SHCNE_FREESPACE = 0x00040000

CONNECT_TEMPORARY = 0x00000004

FILE_READ_DATA = 0x1

SHCNE_UPDATEITEM = 0x00002000
SHCNF_PATH = 0x0005
SHCNF_FLUSHNOWAIT = 0x3000

ERROR_NETNAME_DELETED = 64
ERROR_BAD_NET_NAME = 67
ERROR_BAD_NETPATH = 53
