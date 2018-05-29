//
//  ipc_socket.c
//  CrossCloud
//
//  Created by Christoph Hechenblaikner on 11/10/2016.
//  Copyright © 2016 Johannes Innerbichler. All rights reserved.
//

#include "ipc_socket.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <string.h>
#include <errno.h>

// define errno macro
extern int errno;

int openUnixSocketToCore(const char* unixSocketPath)
{
    // defining address with family, path and len (!! bsd specific !!)
    struct sockaddr_un server_address;
    server_address.sun_family = AF_UNIX;
    strcpy(server_address.sun_path, unixSocketPath);
    server_address.sun_len = SUN_LEN(&server_address);
    
    // creating socket
    int socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if(socket_fd < 0)
    {
        //todo error handling
        int error = errno;
        fprintf(stderr, "Error creating socket: %d \n", error);
        
        return -1;
    }
    
    // connecting to server
    int connection_success = connect(socket_fd, (struct sockaddr*) &server_address, sizeof(server_address));
    if (connection_success < 0)
    {
        //todo error handling
        int error = errno;
        fprintf(stderr, "Error connecting: %d \n", error);
        return -1;
    }
    
    // sending data
    //send(socket_fd, "Hello World\r\n", 13, 0);
    
    return socket_fd;
}

int main(void)
{
    int result = openUnixSocketToCore("/Users/Christoph/Library/Group Containers/crosscloud.ui.findersync/unix_socket");
    fprintf(stdout, "Got result: %d \n", result);
}
