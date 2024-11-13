import socket
import time
import os
import numpy as np
from GBN_SR import *

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.bind(('', 8000))
server_address = ('10.219.136.151', 8888)

# Protocol configuration
GBN_or_SR = 'SR'
Packet_or_TO = 'P'
sthresh = 20000
n = 4
to = 1
temp = GBN_SR(win_size=n, max_size=512, files_dir=r'/home/jingkai/NET/',congestion_control=1)
server_files = ['server_30K.txt', 'server_7M.txt', 'server_700K.png', 'server_200K.pdf', 'server_8M.mp4']
client_files = ['bomb2.tar', 'examples.txt', 'client_12M.pdf']
expectedseqnum = 0
now_seqnum_send = 0
now_seqnum_recv = 0

def download_file():
    """
    Client downloads a file from the server
    """
    global client_socket, now_seqnum_send, now_seqnum_recv, expectedseqnum, drop_flag, temp

    print('<Server file list>')
    for i in range(len(server_files)):
        print(i + 1, end='. ')
        print(server_files[i])
    send_data = input('Enter the file number to download: ').strip()
    # Update client file list and create the file to download
    filename = server_files[int(send_data) - 1]
    client_files.append(filename)
    Receive_File = open(filename, 'wb', buffering=0)
    if GBN_or_SR == 'GBN':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=1, sr=0, data=filename.encode()).to_packet(), server_address)
    elif GBN_or_SR == 'SR':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=0, sr=1, data=filename.encode()).to_packet(), server_address)

    now_seqnum_send += 1
    # Initialization
    expectedseqnum = 0
    drop_flag = 0
    fin_num = -1
    flag = 0
    print('File download started...')
    print('---------------------------------------------------')
    sr_buffer = []
    sr_buffer_index = []
    start = time.time()
    while True:
        packet, addr = client_socket.recvfrom(1024)
        packet_obj = Packet_to_Object(packet)
        now_seqnum_recv = packet_obj.seqnum

        if GBN_or_SR == 'GBN':
            if now_seqnum_recv == expectedseqnum:
                # In sequence, return ACK, write to file
                print('Received expected packet ', now_seqnum_recv, ' ^_^')
                client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, acknum=now_seqnum_recv, gbn=1, sr=0, ack=1).to_packet(), server_address)
                print('Sending ACK:', now_seqnum_recv)
                # Completion flag
                if packet_obj.fin == 1:
                    break
                else:
                    Receive_File.write(packet_obj.data)
                expectedseqnum += 1
            else:
                # Out of sequence, discard
                print('Received wrong packet ', now_seqnum_recv, ', drop it!')
        elif GBN_or_SR == 'SR':
            if now_seqnum_recv >= expectedseqnum:
                # In sequence, return ACK, write to file
                print('Received expected packet ', now_seqnum_recv, ' ^_^')
                client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, acknum=now_seqnum_recv, gbn=0, sr=1, ack=1).to_packet(), server_address)
                print('Sending ACK:', now_seqnum_recv)
                if now_seqnum_recv == expectedseqnum:
                    # Completion flag
                    if packet_obj.fin == 1:
                            break
                    else:
                        Receive_File.write(packet_obj.data)
                        expectedseqnum += 1
                        while expectedseqnum in sr_buffer_index:
                            Receive_File.write(sr_buffer[sr_buffer_index.index(expectedseqnum)])
                            if expectedseqnum == fin_num:
                                flag = 1
                                break
                            expectedseqnum += 1
                        if flag == 1:
                            break
                elif now_seqnum_recv > expectedseqnum:
                    sr_buffer_index.append(now_seqnum_recv)
                    sr_buffer.append(packet_obj.data)
                    if packet_obj.fin == 1:
                        fin_num = now_seqnum_recv
    end = time.time()
    print('---------------------------------------------------')
    print('File %s downloaded successfully!' % filename)
    print('With method:', GBN_or_SR)
    time_cost = (end - start) * 1000
    print('Transfer time: %.4f ms' % time_cost, end=', ')
    file_size = os.path.getsize(os.path.abspath(filename))
    print('Average transfer rate: %.4f B/s\n' % (file_size / time_cost * 1000))

def upload_file():
    """
    Client uploads a file to the server
    """
    global client_socket, now_seqnum_send, now_seqnum_recv, expectedseqnum, drop_flag, temp

    print('<Local file list>')
    for i in range(len(client_files)):
        print(i + 1, end='. ')
        print(client_files[i])
    up = input('Enter the file number to upload: ').strip()
    # Update server file list
    filename = client_files[int(up) - 1]
    print("upload: ",filename)
    server_files.append(filename)
    if GBN_or_SR == 'GBN':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=1, sr=0, data=filename.encode()).to_packet(), server_address)
    elif GBN_or_SR == 'SR':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=0, sr=1, data=filename.encode()).to_packet(), server_address)
    print('File upload started...')
    print('---------------------------------------------------')
    start = time.time()
    packets = File_to_Packets(temp, filename)
    origin_size = File_Size(temp, filename)
    # Initialization
    base = 0
    now_seqnum = 0
    upload_size = 0
    ack = -1
    # Send data packets
    if GBN_or_SR == 'GBN':
        while True:
            # Send when there is space in the window
            while now_seqnum < base + temp.win_size and now_seqnum < len(packets):
                packets[now_seqnum].set_seqnum(now_seqnum)
                client_socket.sendto(packets[now_seqnum].to_packet(), server_address)
                upload_size += packets[now_seqnum].get_len()
                print('Sending packet:', now_seqnum)
                if base == now_seqnum:
                    print("     setting time out...")
                    client_socket.settimeout(to)
                now_seqnum += 1
            # Receive ACK
            
            try:
                ack, addr = client_socket.recvfrom(1024)
                ack_obj = Packet_to_Object(ack)
                if ack_obj.ack == 1:
                    ack = int(ack_obj.acknum)
                    print('Received ACK:', ack)
                    base = ack + 1
            except socket.timeout:
                print('     Timeout back to:',base)
                now_seqnum = base
            if ack == len(packets) - 1:
                break
    else:
        ack_list = []
        while True:
            while now_seqnum < base + temp.win_size and now_seqnum < len(packets):
                if now_seqnum not in ack_list: 
                    packets[now_seqnum].set_seqnum(now_seqnum)
                    client_socket.sendto(packets[now_seqnum].to_packet(), server_address)
                    upload_size += packets[now_seqnum].get_len()
                    print('Sending packet:', now_seqnum)
                if base == now_seqnum:
                    print("     reset time out...")
                    client_socket.settimeout(to)
                now_seqnum += 1
            
            try:
                ack, addr = client_socket.recvfrom(1024)
                ack_obj = Packet_to_Object(ack)
                if ack_obj.ack == 0:
                    continue
                ack = int(ack_obj.acknum)
                ack_list.append(ack)
                print('Received ACK:', ack)
                if base == ack:
                    base = ack + 1
                    while base in ack_list:
                        base += 1
            except socket.timeout:
                print('     Timeout back to:',base)
                now_seqnum = base
            if base == len(packets):
                break
    end = time.time()
    print('---------------------------------------------------')
    print('File %s uploaded successfully!' % filename)
    print('With method:', GBN_or_SR)
    time_cost = (end - start) * 1000
    print('Transfer time: %.4f ms' % time_cost, end=', ')
    file_size = os.path.getsize(os.path.abspath(filename))
    print('Average transfer rate: %.4f B/s\n' % (file_size / time_cost * 1000))
    print('Transfer efficiency:%.4f' %(origin_size / upload_size))
    
if __name__ == '__main__':
    while True:
        print('<Protocol configuration>')
        GBN_or_SR = input('Enter the protocol to use (GBN or SR): ').strip()
        n = int(input('Enter the window size N: '))
        to = int(input('Enter the timeout TO (ms): '))
        temp.set_protocol(GBN_or_SR)
        temp.set_win(n)
        temp.set_to(to)
        print('\n<Transfer type>')
        print('1. Download file')
        print('2. Upload file')
        choice = input('Enter the corresponding number: ').strip()
        print('---------------------------------------------------')
        choice = int(choice)
        if choice == 1:
            download_file()
        elif choice == 2:
            upload_file()
