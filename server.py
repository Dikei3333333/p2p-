# server.py - 中央服务器用于节点发现
import socket
import threading
import time
import queue  
import threading
from collections import defaultdict

SERVER_IP = '10.4.63.217'  # 服务器监听地址
SERVER_PORT = 5555      # 服务器监听端口
BUFFER_SIZE = 1024      # 缓冲区大小

class Server:
    def __init__(self):
        self.clients = defaultdict(dict)  # 存储客户端信息
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, SERVER_PORT))
        print(f"Server listening on {SERVER_IP}:{SERVER_PORT}")

    def handle_client(self, data, addr):
        """处理客户端请求"""
        parts = data.decode().split('|')
        cmd = parts[0]
        
        if cmd == 'REGISTER':  # 客户端注册
            client_id = parts[1]
            self.clients[client_id]['addr'] = addr
            print(f"Client {client_id} registered from {addr}")
            self.sock.sendto(b'OK', addr)
            
        elif cmd == 'QUERY':  # 查询客户端信息
            target_id = parts[1]
            target = self.clients.get(target_id)
            if target:
                ip, port = target['addr']
                response = f"ADDR|{ip}|{port}".encode()
                self.sock.sendto(response, addr)
            else:
                self.sock.sendto(b'NOT_FOUND', addr)
                
        elif cmd == 'LIST':
            requester_id = parts[1]
            online_users = [uid for uid in self.clients.keys() if uid != requester_id]
            response = f"LIST|{','.join(online_users)}".encode()
            self.sock.sendto(response, addr)        
        
        elif cmd == 'HEARTBEAT':  # 心跳检测
            client_id = parts[1]
            if client_id in self.clients:
                self.clients[client_id]['addr'] = addr
                self.sock.sendto(b'ALIVE', addr)
        
    
    def run(self):
        while True:
            data, addr = self.sock.recvfrom(BUFFER_SIZE)
            threading.Thread(target=self.handle_client, args=(data, addr)).start()

if __name__ == '__main__':
    server = Server()
    server.run()