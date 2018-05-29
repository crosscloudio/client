//
//  ipc_socket.h
//  CrossCloud
//
//  Created by Christoph Hechenblaikner on 11/10/2016.
//  Copyright © 2016 Johannes Innerbichler. All rights reserved.
//

#ifndef ipc_socket_h
#define ipc_socket_h

#include <stdio.h>

int openUnixSocketToCore(const char* unixSocketPath);

#endif /* ipc_socket_h */
