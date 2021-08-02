
import socket
import pickle
from datatable import VideoDeepLink
from tools import getMoreLink
server=socket.socket()
server.bind(('0.0.0.0',519))
server.listen(1)
while True:
    conn,addr=server.accept()
    try:
        data=conn.recv(4096000)
        if len(data)==0:
            break
        vs=getMoreLink(pickle.loads(data))
        conn.sendall(pickle.dumps(vs))
    except:
        print("connet close")
    finally:
        conn.close()
        
