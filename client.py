#!/usr/bin/env python3

import sys
import socket
import selectors
import types
import json
import io
import traceback

import client_lib

sel = selectors.DefaultSelector()

def start_connection(host, port, handle):
    server_addr = (host,port)
    print("Starting connection", handle, "to", server_addr)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #create a socket and set to non-blocking
    sock.setblocking(False)
    sock.connect_ex(server_addr) #start connection to server for current conn
    events = selectors.EVENT_WRITE 
    message = client_lib.Message(sel, sock, server_addr, handle)
    sel.register(sock, events, data=message)

#check if user input was correct
if len(sys.argv) != 4:
    print("usage:", sys.argv[0], "<host> <port> <handle>")
    sys.exit(1)

host, port, handle = sys.argv[1:4]
start_connection(host, int(port), handle)

try:
    while True:
        events = sel.select(timeout=None)
        if events:
            for key, mask in events:
                #print("conn to serv ",key," ",mask)
                message_object = key.data
                try:
                    if mask & selectors.EVENT_READ:
                        message_object.process_read_events(mask)
                        #service_connections_READ(key, mask)
                    if mask & selectors.EVENT_WRITE:
                        message = input("> ")
                        message_object.process_write_events(mask, message)
                        #service_connections_WRITE(key, mask, message)
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{message_object.addr}:\n{traceback.format_exc()}",
                    )
                    message_object.close()
        if not sel.get_map():
            #what does this mean? Only continue if the socket is being monitored
            break
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()