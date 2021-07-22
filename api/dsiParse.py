 # -*- coding: utf-8 -*-
"""
Created on Fri Jul  9 08:56:48 2021

@author: zhkgo
"""

import pickle
import numpy as np
import socket

def connect_socket(HOST='localhost',PORT=8844):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # 定义socket类型，网络通信，TCP
    s.connect((HOST, PORT))  # 要连接的IP与端口
    return s
    # while 1:
    #     data = s.recv(1024)  # 把接收的数据定义为变量
    #     print
    #     data  # 输出变量
    #     s.close()  # 关闭连接

# class DSI_device:
#     def __init__(self, realpart, imagpart):
#         self.r = realpart
#         self.i = imagpart

def read_data(file_path):
    with open(file_path, 'rb') as f:
        data = pickle.load(f)
    return data


def ascall_index(chr):
    return int(chr)


def count_sum(data):
    sum_ = 0
    for i in data:
        sum_ += int(i)
    return sum_


def decode_header(header):
    packet_start = header[:5]
    packet_type = int(header[5])
    packet_length = int(header[6]) + int(ascall_index(header[7]))
    # print(ascall_index(header[7]))
    packet_number = count_sum(header[8:12])
    # print('packet_start:',packet_start,'packet_type:',packet_type,'packet_length:',packet_length,'packet_number:',packet_number)
    return packet_type, packet_length


def decode_event_pack(data):
    event_code = count_sum(data[:4])
    sending_note = count_sum(data[4:8])
    msg_length = count_sum(data[8:12])
    if event_code == 9:
        msg = {"channels": str(data[12:12 + msg_length])[2:-1].replace(" ", "").split(',')}
    elif event_code == 10:
        msg = {"mains frequency,sampling frequency": str(data[12:12 + msg_length])[2:-1].replace(" ", "").split(',')}
    else:
        msg = {'other': str(data[12:12 + msg_length])[2:-1]}
    # print('event_code:',event_code,'sending_note:',sending_note,'msg_length:',msg_length,'msg:')
    return msg_length, msg


def remove_head_mistake(data):
    length_ = 0
    for i in data:
        if chr(i) != '@':
            length_ += 1
            continue
        else:
            break
    return length_


def decode_EEG_sensor(data):
    timestamp = data[:4]
    data_counter = int(data[4])
    ADC_status = data[5:11]
    ch_data = data[11:]
    eeg_data = []
    for i in range(0, len(ch_data), 4):
        # print(ch_data[i:i+4])
        a = np.array(ch_data[i:i + 4])
        a.dtype = np.float32
        a=a.tolist()
        if(abs(a)>100):
            if len(eeg_data)>5:
                a = np.average(eeg_data[-5:])
            else:
                a = 0
        eeg_data.append(a)

    # print('timestamp:',timestamp,'data_counter:',data_counter,'ADC_status:',ADC_status,'ch_data:',ch_data)
    return len(data), eeg_data


# data = read_data('dsi.pkl')

if __name__ == "__main__":

    s = connect_socket()
    # ******************************

    while True:

        data = s.recv(2048)
        count = 0
        while 1:
            try:
                length_ = remove_head_mistake(data[count:])
                count += length_
                packet_header = data[count:12 + count]
                count += 12
                print(packet_header)

                packet_type, packet_length = decode_header(packet_header)
                packet_data = data[count:count + packet_length]
                print(packet_data)
                if packet_type == 5:
                    msg_length, msg = decode_event_pack(packet_data)
                    #print(msg_length, msg, '\n ******************************')
                    #time.sleep(5)
                elif packet_type == 1:
                    msg_length, msg = decode_EEG_sensor(packet_data)
                #print(msg_length, msg, '\n ******************************')
                count += msg_length
            except Exception:
                break
