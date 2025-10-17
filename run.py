
import socket
import re
import os
import time


class server:
    '''
    接收端、输入端开启服务时间相差不能太长
    '''
    def __init__(self,src_dir=None,dst_dir=None,recv_ip=None,port=None,size=1024):
        '''
        :param src_dir: 发送端地址，文件或者目录都可以
        :param dst_dir: 接收端目录，没有时会创建
        :param recv_ip: 接收端ip，需要在同一局域网内
        :param port: 端口，发送端、接收端端口需要一致
        :param size: 流式传输大小
        '''

        '''获取本地'''
        self.host = socket.gethostname()
        self.recv_ip = recv_ip

        '''设置端口'''
        self.port = port
        self.dst_dir = dst_dir
        self.src_dir = src_dir
        self.msg = '等待传输'
        self.size = size

    def accept(self,client,stop_time=3,size=1024):
        info = ''
        t_start = time.time()
        while not info:
            info = client.recv(size)
            if time.time() - t_start > stop_time:
                break
        return info

    def send(self):
        print('等待连接接收端')
        '''创建socket对象'''
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        '''连接服务器， 指定IP和端口'''
        client.connect((self.recv_ip, self.port))

        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
        client.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 60 * 1000, 30 * 1000))

        msg = self.accept(client)
        if not msg:
            raise Exception('未接收到反馈信息')
        if os.path.isdir(self.src_dir):
            for root, dirs, files in os.walk(self.src_dir, True):
                for eachfile in files:
                    file_path = os.path.join(root,eachfile)
                    file_relative_path = os.path.relpath(file_path,self.src_dir)
                    self.send_file(client, file_path, file_relative_path)
        else:
            file_path = self.src_dir
            file_relative_path = re.split('/|\\\\', file_path)[-1]
            self.send_file(client, file_path, file_relative_path)
        client.close()

    def send_file(self,client,file_path,file_relative_path):
        filesize = os.path.getsize(file_path)
        # 先将文件名传过去
        # 编码文件名
        client.send(file_relative_path.encode())
        msg = self.accept(client)
        if not msg:
            raise Exception('未接收到反馈信息')
        # 再将将文件大小传过去
        # 编码文件大小
        client.send(str(filesize).encode())

        size = self.accept(client)
        if not size:
            raise Exception('未接收到反馈信息')
        client.send(self.msg.encode())
        size = int(size.decode())


        '''传输文件'''
        start_time = time.time()
        with open(file_path, 'rb') as f:

            if size == filesize:
                print(f'文件{file_path}已传输完成')
                return
            elif size > filesize:
                raise Exception(f'文件{file_path}接收大小大于原文件大小')

            f.seek(size)
            while True:
                f_data = f.read(self.size)
                # 数据长度不为零，传输继续
                if f_data:
                    client.send(f_data)
                    size += len(f_data)

                    speed = (size) / (time.time() - start_time + 1e-9)
                    print('\r' + '【%s 上传进度】:%s%.2f%%, Speed: %.2fMB/s' % (file_relative_path,'>' * int(size * 50 / filesize), float(size / filesize * 100), float(speed / 1024 / 1024)),end=' ')
                else:
                    msg = self.accept(client)
                    if not msg:
                        raise Exception('未接收到反馈信息')
                    print()
                    break



    def recv(self):

        print('等待传输端传输')
        ''' 创建socket对象'''
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
        client.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 60 * 1000, 30 * 1000))
        '''绑定地址'''
        client.bind((self.host, self.port))
        '''设置最大连接数， 超过后排队'''
        client.listen(12)
        client, addr = client.accept()
        client.send(self.msg.encode())
        while True:
            '''接收文件名,文件大小'''
            filename = self.accept(client)
            if not filename:
                # raise Exception('未接收到反馈信息')
                break
            client.send(self.msg.encode())
            filename = filename.decode()

            filesize = self.accept(client)

            # 解码文件名,文件大小
            filesize = int(filesize.decode())

            file_path = os.path.join(self.dst_dir,filename)
            file_dir = os.path.dirname(file_path)

            if not os.path.exists(file_dir):
                os.makedirs(file_dir)

            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                if size == filesize:
                    print(f'文件{filename}已下载完成')
                else:
                    print(f'文件{filename}:{round(filesize / 1024 / 1024, 2)}MB继续下载')
            else:
                print(f'文件{filename}:{round(filesize / 1024 / 1024, 2)}MB开始下载')
                size = 0

            client.send(str(size).encode())
            msg = self.accept(client)
            if not msg:
                raise Exception('未接收到反馈信息')

            if size == filesize:
                continue

            f = open(file_path, 'ab')
            start_time = time.time()
            while True:
                # 接收数据
                f_data = client.recv(self.size)
                if f_data:
                    size += len(f_data)
                    if size >= filesize:
                        f.write(f_data)
                        client.send(self.msg.encode())
                        speed = (size) / (time.time() - start_time + 1e-9)
                        print('\r' + '【%s 下载进度】:%s%.2f%%, Speed: %.2fMB/s' % (filename, '>' * int(size * 50 / filesize), 100,float(speed / 1024 / 1024)), end=' ')
                        print()
                        break
                    else:
                        f.write(f_data)
                        speed = (size) / (time.time() - start_time + 1e-9)
                        print('\r' + '【%s 下载进度】:%s%.2f%%, Speed: %.2fMB/s' % (filename, '>' * int(size * 50 / filesize), float(size / filesize * 100), float(speed / 1024 / 1024)),end=' ')
            f.close()
        client.close()
        print('全部接收完成')


if __name__ == '__main__':
    # 远程电脑的相关信息
    recv_ip = '10.26.0.2'
    port = 5001
    src_dir = r'D:\work\文档\导购'
    dst_dir = r'D:/'
    sev = server(dst_dir=dst_dir,src_dir=src_dir,recv_ip=recv_ip,port=port)
    sev.send()
    # sev.recv()

