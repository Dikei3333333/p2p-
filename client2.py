# client.py - 改进版P2P客户端
import socket
import time
import queue
import threading

# ================= 配置区域 =================
SERVER_ADDR = ('10.4.63.217', 5555)  # 必须修改为服务器真实IP
BUFFER_SIZE = 1024                      # 网络缓冲区大小
HEARTBEAT_INTERVAL = 45                 # 心跳间隔(秒)
CONN_TIMEOUT = 8                        # 服务器检测超时时间(秒)
# ===========================================

class P2PClient:
    def __init__(self, client_id):
        self.client_id = client_id
        self.peer_addr = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1)
        
        # 状态检测事件
        self.server_ready = threading.Event()
        self.running = True
        
        try:
            # 尝试绑定随机端口
            self.sock.bind(('0.0.0.0', 0))
            print(f"客户端端口: {self.sock.getsockname()[1]}")
        except OSError as e:
            print(f"端口绑定失败: {str(e)}")
            raise
        
        # 启动核心线程
        threading.Thread(target=self._network_listener, daemon=True).start()
        threading.Thread(target=self._input_handler, daemon=True).start()
        
        # 立即检测服务器状态
        if not self._check_server_connection():
            print("\033[31m错误：无法连接中继服务器！请检查：\033[0m")
            print(f"1. 服务器地址是否正确：{SERVER_ADDR[0]}:{SERVER_ADDR[1]}")
            print("2. 服务器程序是否正在运行")
            print("3. 防火墙是否开放UDP端口")
            self.running = False
            return
        
        # 注册到服务器
        self._send_to_server(f"REGISTER|{client_id}")
        self._show_help()

    def _check_server_connection(self):
        """检测服务器是否可达"""
        print("\n\033[36m正在检测服务器状态...\033[0m")
        retry_count = 0
        while retry_count < 3 and self.running:
            try:
                # 发送空测试包
                test_payload = b'TEST_CONNECTION'
                self.sock.sendto(test_payload, SERVER_ADDR)
                # 等待响应
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                if addr == SERVER_ADDR:
                    print("\033[32m服务器连接正常！\033[0m")
                    return True
            except socket.timeout:
                retry_count += 1
                print(f"尝试 {retry_count}/3...")
            except Exception as e:
                print(f"连接异常: {str(e)}")
                return False
        return False

    # ================= 核心功能 =================
    def _send_to_server(self, message):
        """发送消息到中央服务器"""
        self.sock.sendto(message.encode(), SERVER_ADDR)

    def send_to_peer(self, message):
        """发送消息到对等节点"""
        if self.peer_addr:
            self.sock.sendto(message.encode(), self.peer_addr)
            print(f"[发送成功] -> {self.peer_addr}")
        else:
            print("错误：尚未连接任何对等节点")

    def query_peer(self, peer_id):
        """查询对端地址"""
        self._send_to_server(f"QUERY|{peer_id}")
        try:
            data, _ = self.sock.recvfrom(BUFFER_SIZE)
            if data.startswith(b'ADDR'):
                _, ip, port = data.decode().split('|')
                self.peer_addr = (ip, int(port))
                print(f"成功获取对端地址: {self.peer_addr}")
                # 主动发起打洞
                self.sock.sendto(b'PUNCH', self.peer_addr)
            else:
                print("错误：目标节点不存在")
        except socket.timeout:
            print("查询超时，请检查网络连接")

    def list_users(self):
        """获取在线用户列表"""
        self._send_to_server(f"LIST|{self.client_id}")
        try:
            data, _ = self.sock.recvfrom(BUFFER_SIZE)
            if data.startswith(b'LIST'):
                _, users = data.decode().split('|', 1)
                return [u for u in users.split(',') if u]
            return []
        except socket.timeout:
            print("获取用户列表超时")
            return []

    # ================= 线程方法 =================
    def _network_listener(self):
        """网络监听线程"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                # 转义序列保持输入行整洁
                print(f"\n\033[33m[来自 {addr[0]}:{addr[1]}]\033[0m {data.decode()}")
                print("> ", end='', flush=True)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"\n网络错误: {str(e)}")
                break

    def _heartbeat_sender(self):
        """心跳发送线程"""
        while self.running:
            self._send_to_server(f"HEARTBEAT|{self.client_id}")
            time.sleep(HEARTBEAT_INTERVAL)

    def _input_handler(self):
        """输入处理线程"""
        while self.running:
            try:
                cmd = input()
                self.input_queue.put(cmd)
            except (KeyboardInterrupt, EOFError):
                self.running = False
                break

    # ================= 界面辅助 =================
    def _show_help(self):
        """显示帮助信息"""
        help_text = """
        ======== 命令手册 ========
        /connect <ID>  连接其他用户
        /list          查看在线用户
        /help          显示本帮助
        /exit          退出程序
        直接输入内容发送消息
        ==========================
        """
        print("\033[34m" + help_text + "\033[0m")

if __name__ == '__main__':
    # 用户引导
    print("\n\033[32m=== P2P联机工具 ===\033[0m")
    client_id = input("请输入你的客户端ID: ").strip()
    
    # 初始化客户端
    try:
        client = P2PClient(client_id)
        if not client.running:
            exit(1)
        
        # 主循环前进行最终状态确认
        if not client.server_ready.wait(timeout=CONN_TIMEOUT):
            print("\033[31m错误：服务器响应超时，请检查服务器状态！\033[0m")
            exit(1)
    
    # 主命令循环
        while client.running:
            try:
                # 显示动态提示符
                print("> ", end='', flush=True)
                cmd = client.input_queue.get(timeout=2)
                print("\033[1A\033[K", end='')  # 清除提示符
            
                if cmd.startswith('/connect '):
                    _, peer_id = cmd.split(' ', 1)
                    client.query_peer(peer_id)
                elif cmd == '/list':
                    users = client.list_users()
                    if users:
                        print("\n在线用户:")
                        for user in users:
                            print(f"  - {user}")
                    else:
                        print("\n当前没有其他在线用户")
                elif cmd == '/help':
                    client._show_help()
                elif cmd == '/exit':
                    client.running = False
                else:
                    client.send_to_peer(cmd)
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                client.running = False
    except KeyboardInterrupt:
        print("\n用户强制退出")
    except Exception as e:
        print(f"\033[31m致命错误: {str(e)}\033[0m")