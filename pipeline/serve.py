import os, sys, http.server, RangeHTTPServer

# Serve output folder with range requests/cors support for testing purposes
class CORSRequestHandler(RangeHTTPServer.RangeRequestHandler):
    def end_headers (self):
        self.send_header('Access-Control-Allow-Origin', '*')
        RangeHTTPServer.RangeRequestHandler.end_headers(self)
        
def start_server():
    httpd = http.server.HTTPServer(('localhost', 5501), CORSRequestHandler)
    httpd.serve_forever()

if __name__ == '__main__':
    start_server()