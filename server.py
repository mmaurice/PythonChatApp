#!/usr/bin/env python3 
import sys
import socket
import selectors
import types
import io
import json
import traceback

import server_lib

#create selector for listening socket
sel = selectors.DefaultSelector()

##need a function to accept connections on
def Accept_Wrapper(sock):
    conn, addr = sock.accept()
    print("Accepted connection from", (addr))
    conn.setblocking(False)
    #setup data, and event to register the conn sock with sel.register()
    message = server_lib.Message(sel, conn, addr)
    events = selectors.EVENT_READ
    sel.register(conn, events, data=message)

#check to make sure 3 args were given
if len(sys.argv) != 3:
    print("usage:", sys.argv[0], "<host> <port>")
    sys.exit(1)

#create port and server from cli input
host, port = sys.argv[1], int(sys.argv[2])
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((host,port))
lsock.listen(100)
print("Listening on", (host, port))
lsock.setblocking(False)
sel.register(lsock, events=selectors.EVENT_READ, data=None)

try:
    while True:
        events = sel.select(timeout=None)
        for key, mask in events:
            if key.data is None:
                #accept function args - key.fileobj, no data in mask
                Accept_Wrapper(key.fileobj)
            else:
                #server conn function
                message_object =  key.data
                try:
                    if mask & selectors.EVENT_READ:
                        message_object.process_read_events(mask)
                        #Service_Connection_READ(key, mask)
                    if mask & selectors.EVENT_WRITE:
                        message_object.process_write_events(mask)
                        #Service_Connection_WRITE(key, mask)
                    #Service_Connection(key,mask)
                    #print("conn to serv ",key," ",mask)
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{message_object.addr}:\n{traceback.format_exc()}",
                    )
                    message_object.close()
except KeyboardInterrupt:
    print("caught keyboard interrupt exiting")
finally:
    sel.close()