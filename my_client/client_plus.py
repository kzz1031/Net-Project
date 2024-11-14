import socket
import time
import os
import numpy as np
from GBN_SR import *

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.bind(('', 8000))
server_address = ('47.251.161.108', 8888)
# server_address = ('10.223.78.176', 8888)
# server_address = ('192.168.3.87', 8888)
# Protocol configuration
GBN_or_SR = 'SR'
Packet_or_TO = 'P'

n = 4
to = 1
temp = GBN_SR(win_size=n, max_size=512, files_dir=r'/home/jingkai/NET/',congestion_control=1)
server_files = ['server_30K.txt', 'server_200K.pdf', 'server_700K.png','server_8M.mp4', 'server_4M.pdf', 'server_2M.pdf']
client_files = ['bomb2.tar', 'client_30K.txt','client_200K.pdf', 'examples.txt', 'client_12M.pdf', 'client_400K.txt','client_700K.png']
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
    print(temp.packet_or_To)
    if GBN_or_SR == 'GBN':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=1, sr=0, packet_or_To=temp.packet_or_To, fin=2,data=filename.encode()).to_packet(), server_address)
    elif GBN_or_SR == 'SR':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=0, sr=1, packet_or_To=temp.packet_or_To, fin=2,data=filename.encode()).to_packet(), server_address)
    
    base_start = time.time()
    base_end = 0
    print('Waiting for server acknowledgment...')
    client_socket.settimeout(2)  # Set timeout to 2 seconds, adjust as needed
    try:
        ack, addr = client_socket.recvfrom(1024)
        ack_obj = Packet_to_Object(ack)
        print(addr, ack_obj.ack)
        if ack_obj.ack == 1:
            base_end = time.time()
            print('Received ACK for filename')
        else:
            print("No such file")
            #return download_file()
    except socket.timeout:
        print('Timeout waiting for ACK of filename, resending...')
        return download_file()  # Resend filename
    
    now_seqnum_send += 0
    # Initialization
    expectedseqnum = 0
    baseseq = 0
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
                if expectedseqnum > 0:
                    client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, acknum=expectedseqnum - 1, ack=1).to_packet(), server_address)
                # Out of sequence, discard
                print('Received wrong packet ', now_seqnum_recv, ', drop it!')
        elif GBN_or_SR == 'SR':
            if now_seqnum_recv >= expectedseqnum:
                # In sequence, return ACK, write to file
                print('Received expected packet ', now_seqnum_recv, ' ^_^', "expected packet: ", expectedseqnum)
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
            else:
                print('Received expected packet ', now_seqnum_recv, ' ^_^')
                client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, acknum=now_seqnum_recv, gbn=0, sr=1, ack=1).to_packet(), server_address)
                print('Sending ACK:', now_seqnum_recv)
    end = time.time()
    print('---------------------------------------------------')
    print('File %s downloaded successfully!' % filename)
    print(f'With method:{GBN_or_SR} {Packet_or_TO} {temp.packet_or_To}')
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
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=1, sr=0, fin=2,data=filename.encode()).to_packet(), server_address)
    elif GBN_or_SR == 'SR':
        client_socket.sendto(GBN_SR(seqnum=now_seqnum_send, gbn=0, sr=1, fin=2,data=filename.encode()).to_packet(), server_address)
    base_start = time.time()
    base_end = 0
    print('Waiting for server acknowledgment...')
    client_socket.settimeout(2)  # Set timeout to 2 seconds, adjust as needed
    try:
        ack, addr = client_socket.recvfrom(1024)
        ack_obj = Packet_to_Object(ack)
        if ack_obj.ack == 1:
            base_end = time.time()
            print('Received ACK for filename')
    except socket.timeout:
        print('Timeout waiting for ACK of filename, resending...')
        return upload_file()  # Resend filename
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
    temp.set_win(8)
    count = 0
    dup_ack = 0
    sthresh = 20000
    packet_send_times = {} 
    base_rtt = base_end - base_start
    min_rtt = float('inf')
    alpha = 150
    beta = 200
    # Send data packets
    if GBN_or_SR == 'GBN':
        while True:   
            # Send when there is space in the window
            while now_seqnum < base + temp.win_size and now_seqnum < len(packets) - 1:
                if base == now_seqnum:
                    print("     setting time out...")
                    client_socket.settimeout(temp.to/1000)
                packets[now_seqnum].set_seqnum(now_seqnum)
                client_socket.sendto(packets[now_seqnum].to_packet(), server_address)
                packet_send_times[now_seqnum] = time.time() 
                upload_size += packets[now_seqnum].get_len()
                print(f'Sending packet:{now_seqnum}, window size:{temp.win_size}')
                now_seqnum += 1
            # Receive ACK
            if base == len(packets) - 1:
                packets[now_seqnum].set_seqnum(now_seqnum)
                client_socket.sendto(packets[now_seqnum].to_packet(), server_address)
                packet_send_times[now_seqnum] = time.time()
                print(f'Sending packet:{now_seqnum}, window size:{temp.win_size}') 

            try:
                ack, addr = client_socket.recvfrom(1024)
                ack_obj = Packet_to_Object(ack)
                if ack_obj.ack == 1:
                    ack = int(ack_obj.acknum)
                    print('Received ACK:', ack,' now_seqnum: ', now_seqnum)
                    
                    if ack in packet_send_times:
                        rtt = time.time() - packet_send_times[ack]
                        min_rtt = min(min_rtt, rtt)
                        if rtt < base_rtt and rtt != 0:
                            base_rtt = rtt
                        if base_rtt is None:
                            base_rtt = rtt
                        else:
                            if Packet_or_TO == 'T':
                                # if (1/rtt) < (1/base_rtt)*1.2:
                                #     temp.win_size = max(temp.win_size - 1, 2)
                                # elif (1/rtt) > (1/base_rtt)*0.8:
                                #     temp.win_size = min(temp.win_size + 1, sthresh)
                                #     temp.win_size = min(temp.win_size + 1, sthresh)
                                if temp.win_size*(1/base_rtt - 1/rtt) > beta:
                                    temp.win_size = max(temp.win_size - 1, 2)
                                elif temp.win_size*(1/base_rtt - 1/rtt) < alpha:
                                    temp.win_size = min(temp.win_size + 1, sthresh)

                    if base == ack + 1:
                        dup_ack += 1
                        if dup_ack == 3:
                            client_socket.settimeout(temp.to/1000)
                            now_seqnum = base
                            if Packet_or_TO == 'P':
                                temp.win_size = max(int(temp.win_size/2), 2)
                                sthresh = temp.win_size
                            print("     Fast recovery: ",base)
                            dup_ack = -12345 # three times dupacks trigger resend packet
                        continue
                    dup_ack = 0
                    base = ack + 1
                    if Packet_or_TO == 'P': #Congestion based on lose packet
                        if temp.win_size < sthresh: #slow start
                            temp.win_size += 1
                            print("window size +1")
                        else:
                            count += 1
                            if count >= temp.win_size: 
                                temp.win_size += 1
                                count = 0

            except socket.timeout:
                print('     Timeout back to:',base)
                # temp.win_size = max(temp.win_size/2, 2)
                # sthresh = temp.win_size
                now_seqnum = base
            if ack == len(packets) - 1:
                break
    else:
        ack_list = []
        while True:
            while now_seqnum < base + temp.win_size and now_seqnum < len(packets) - 1:
                if base == now_seqnum:
                    print("     reset time out...")
                    client_socket.settimeout(temp.to/1000)
                if now_seqnum not in ack_list: 
                    packets[now_seqnum].set_seqnum(now_seqnum)
                    client_socket.sendto(packets[now_seqnum].to_packet(), server_address)
                    packet_send_times[now_seqnum] = time.time() 
                    upload_size += packets[now_seqnum].get_len()
                    print(f'Sending packet:{now_seqnum}, window size:{temp.win_size}')
                now_seqnum += 1

            if base == len(packets) - 1:
                packets[now_seqnum].set_seqnum(now_seqnum)
                client_socket.sendto(packets[now_seqnum].to_packet(), server_address)
                packet_send_times[now_seqnum] = time.time() 
                print(f'Sending packet:{now_seqnum}, window size:{temp.win_size}')

            try:
                ack, addr = client_socket.recvfrom(1024)
                ack_obj = Packet_to_Object(ack)
                if ack_obj.ack == 0:
                    continue
                ack = int(ack_obj.acknum)
                ack_list.append(ack)
                print('Received ACK:', ack)

                if ack in packet_send_times:
                        rtt = time.time() - packet_send_times[ack]
                        min_rtt = min(min_rtt, rtt)
                        if rtt < base_rtt and rtt != 0:
                            base_rtt = rtt
                        if base_rtt is None:
                            base_rtt = rtt
                        else:
                            if Packet_or_TO == 'T':
                                print("   1/rtt: ", 1/rtt)
                                # if (1/rtt) < (1/base_rtt)*0.8:
                                #     temp.win_size = max(temp.win_size - 1, 2)
                                # elif (1/rtt) > (1/base_rtt):
                                #     temp.win_size = min(temp.win_size + 1, sthresh)
                                #     temp.win_size = min(temp.win_size + 1, sthresh)
                                if temp.win_size*(1/base_rtt - 1/rtt) > beta:
                                    temp.win_size = max(temp.win_size - 1, 2)
                                elif temp.win_size*(1/base_rtt - 1/rtt) < alpha:
                                    temp.win_size = min(temp.win_size + 1, sthresh)

                if Packet_or_TO == 'P': #Congestion based on lose packet
                    if temp.win_size < sthresh:
                        temp.win_size += 1     
                    else:
                        count += 1
                        if count >= temp.win_size:
                            temp.win_size += 1
                            count = 0
                if base == ack:
                    base = ack + 1
                    while base in ack_list:
                        base += 1
            except socket.timeout:
                if Packet_or_TO == 'P':
                    temp.win_size = max(int(temp.win_size/2), 2)
                    sthresh = temp.win_size
                client_socket.settimeout(temp.to/1000)
                print('     Timeout back to:',base)
                now_seqnum = base
            if base == len(packets):
                break
    end = time.time()
    print('---------------------------------------------------')
    print('File %s uploaded successfully!' % filename)
    print(f'With method:{GBN_or_SR},{Packet_or_TO}')
    time_cost = (end - start) * 1000
    print('Transfer time: %.4f ms' % time_cost, end=', ')
    file_size = os.path.getsize(os.path.abspath(filename))
    print('Average transfer rate: %.4f B/s' % (file_size / time_cost * 1000))
    print('Transfer efficiency:%.4f' %(origin_size / upload_size))
    print(f'base rtt: {1/base_rtt}')
    
if __name__ == '__main__':
    while True:
        print('<Protocol configuration>')
        GBN_or_SR = input('Enter the protocol to use (GBN or SR): ').strip()
        Packet_or_TO = input('Congestion control based on packet(P) loss or latency(T):')
        #n = int(input('Enter the window size N: '))
        # to = int(input('Enter the timeout TO (ms): '))
        temp.set_protocol(GBN_or_SR)
        temp.set_congestion_protocol(Packet_or_TO)
        #temp.set_win(n)
        temp.set_to(200)
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
