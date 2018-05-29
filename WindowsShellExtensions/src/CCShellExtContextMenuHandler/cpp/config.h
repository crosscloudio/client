/**
* (C) 2016 CrossCloud GmbH
*/

#ifndef CC_CONFIG_H
#define CC_CONFIG_H

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#undef WIN32_LEAN_AND_MEAN

#include <winsock2.h>

#pragma comment(lib, "ws2_32.lib")



#ifdef _DEBUG
#define LOGGING
#endif

#endif //CC_CONFIG_H



