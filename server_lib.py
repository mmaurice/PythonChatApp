import sys
import selectors
import json
import io
import struct


class Message:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.handle = None
        self.recv_buffer = b""
        self.send_buffer = b""
        self.message_queue = b""
        self.message_queued = False
        self.jsonheader_len = None
        self.jsonheader = None
        self.content = None

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def process_read_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()

    def read(self):
        self._read()

        if self.jsonheader_len is None:
            self.process_protoheader()

        if self.jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.content is None:
                self.process_content()
                self.jsonheader_len = None
                self.jsonheader = None
                self.content = None
                events = selectors.EVENT_WRITE
                self.selector.modify(self.sock,events,data=self)
    
    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self.recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def process_protoheader(self):
        hrdlen = 2
        if len(self.recv_buffer.decode()) >= hrdlen:
            self.jsonheader_len = self.recv_buffer[:hrdlen].decode()
            self.recv_buffer = self.recv_buffer[hrdlen:]
    
    def process_jsonheader(self):
        hrdlen = int(self.jsonheader_len)
        if len(self.recv_buffer.decode()) >= hrdlen:
            #need to get handle and json_header_len from the json object, 
            recv_json_data_raw = self.recv_buffer[:hrdlen]
            self.jsonheader = self._json_decode(recv_json_data_raw,'UTF-8')
            self.recv_buffer = self.recv_buffer[hrdlen:]

    def process_content(self):
        content_len = self.jsonheader["content-len"]
        if not len(self.recv_buffer.decode()) >= content_len:
            return
        data = self.recv_buffer[:content_len]
        self.recv_buffer = self.recv_buffer[content_len:]
        self.content = data
        print(self.content)
        self.message_queue = self.content
        self.content = None
        #self.close()
        #THis is where the server is different. Once I've processed the data in ther recv_buffer. I need to populate the send_buffer with that data.

    def process_write_events(self, mask):
        if mask & selectors.EVENT_WRITE:
            self.write()
    
    def write(self):
        if not self.message_queued:
            self.relay_message()

        self._write()

        if self.message_queued:
            if not self.send_buffer:
                self.message_queued = False
                events = selectors.EVENT_READ
                self.selector.modify(self.sock,events,data=self)
    
    def _write(self):
        if self.send_buffer:
            print("sending", repr(self.send_buffer), "to", self.addr)
            try:
                # Should be ready to write
                sent = self.sock.send(self.send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self.send_buffer = self.send_buffer[sent:]

    def relay_message(self):
        #Content - str to bytes
        CONTENT =  self.message_queue
        self.message_queue = None
        #JSON_Header - JSON to bytes
        json_data= {
            "content-len":len(CONTENT), 
            }
        JSON_HEADER = json.dumps(json_data).encode()
        #Header - int to bytes
        HEADER = len(JSON_HEADER)

        self.send_buffer += str(HEADER).encode()
        self.send_buffer += JSON_HEADER
        self.send_buffer += CONTENT
        self.message_queued = True

    def close(self):
        print("closing connection to", self.addr)
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                "error: selector.unregister() exception for",
                f"{self.addr}: {repr(e)}",
            )

        try:
            self.sock.close()
        except OSError as e:
            print(
                "error: socket.close() exception for",
                f"{self.addr}: {repr(e)}",
            )
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None