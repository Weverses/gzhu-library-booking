"""
CAS登录DES加密算法
用于加密账号密码提交请求
"""

def generate_keys(key_byte):
    key = [0] * 56
    keys = [[] for _ in range(16)]
    loop = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]
    
    for i in range(7):
        for j, k in zip(range(8), range(7, -1, -1)):
            key[i*8+j] = key_byte[8*k+i]
    
    for i in range(16):
        temp_left = 0
        temp_right = 0
        for j in range(loop[i]):
            temp_left = key[0]
            temp_right = key[28]
            for k in range(27):
                key[k] = key[k+1]
                key[28+k] = key[29+k]
            key[27] = temp_left
            key[55] = temp_right
        
        temp_key = [0] * 48
        perm = [13, 16, 10, 23, 0, 4, 2, 27, 14, 5, 20, 9, 22, 18, 11, 3, 25, 7, 15, 6, 26, 19, 12, 1, 
                40, 51, 30, 36, 46, 54, 29, 39, 50, 44, 32, 47, 43, 48, 38, 55, 33, 52, 45, 41, 49, 35, 28, 31]
        
        for m in range(48):
            temp_key[m] = key[perm[m]]
        
        keys[i] = temp_key[:]
    
    return keys

def init_permute(original_data):
    ip_byte = [0] * 64
    for i, m, n in zip(range(4), range(1, 9, 2), range(0, 9, 2)):
        for j, k in zip(range(7, -1, -1), range(8)):
            ip_byte[i*8+k] = original_data[j*8+m]
            ip_byte[i*8+k+32] = original_data[j*8+n]
    return ip_byte

def expand_permute(right_data):
    ep_byte = [0] * 48
    for i in range(8):
        if i == 0:
            ep_byte[i*6+0] = right_data[31]
        else:
            ep_byte[i*6+0] = right_data[i*4-1]
        ep_byte[i*6+1] = right_data[i*4+0]
        ep_byte[i*6+2] = right_data[i*4+1]
        ep_byte[i*6+3] = right_data[i*4+2]
        ep_byte[i*6+4] = right_data[i*4+3]
        if i == 7:
            ep_byte[i*6+5] = right_data[0]
        else:
            ep_byte[i*6+5] = right_data[i*4+4]
    return ep_byte

def xor(byte_one, byte_two):
    return [a ^ b for a, b in zip(byte_one, byte_two)]

def s_box_permute(expand_byte):
    s_box_byte = [0] * 32
    
    s1 = [
        [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
        [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
        [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
        [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13]
    ]
    
    s2 = [
        [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
        [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
        [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
        [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9]
    ]
    
    s3 = [
        [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
        [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
        [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
        [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12]
    ]
    
    s4 = [
        [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
        [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
        [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
        [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14]
    ]
    
    s5 = [
        [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
        [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
        [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
        [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3]
    ]
    
    s6 = [
        [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
        [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
        [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
        [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13]
    ]
    
    s7 = [
        [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
        [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
        [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
        [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12]
    ]
    
    s8 = [
        [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
        [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
        [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
        [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]
    ]
    
    s_boxes = [s1, s2, s3, s4, s5, s6, s7, s8]
    
    for m in range(8):
        i = expand_byte[m*6+0]*2 + expand_byte[m*6+5]
        j = (expand_byte[m*6+1]*8 + expand_byte[m*6+2]*4 + 
             expand_byte[m*6+3]*2 + expand_byte[m*6+4])
        binary = format(s_boxes[m][i][j], '04b')
        for n in range(4):
            s_box_byte[m*4+n] = int(binary[n])
    
    return s_box_byte

def p_permute(s_box_byte):
    p_box_permute = [0] * 32
    perm = [15, 6, 19, 20, 28, 11, 27, 16, 0, 14, 22, 25, 4, 17, 30, 9,
            1, 7, 23, 13, 31, 26, 2, 8, 18, 12, 29, 5, 21, 10, 3, 24]
    
    for i in range(32):
        p_box_permute[i] = s_box_byte[perm[i]]
    
    return p_box_permute

def finally_permute(end_byte):
    fp_byte = [0] * 64
    perm = [39, 7, 47, 15, 55, 23, 63, 31, 38, 6, 46, 14, 54, 22, 62, 30,
            37, 5, 45, 13, 53, 21, 61, 29, 36, 4, 44, 12, 52, 20, 60, 28,
            35, 3, 43, 11, 51, 19, 59, 27, 34, 2, 42, 10, 50, 18, 58, 26,
            33, 1, 41, 9, 49, 17, 57, 25, 32, 0, 40, 8, 48, 16, 56, 24]
    
    for i in range(64):
        fp_byte[i] = end_byte[perm[i]]
    
    return fp_byte

def enc(data_byte, key_byte):
    keys = generate_keys(key_byte)
    ip_byte = init_permute(data_byte)
    ip_left = ip_byte[:32]
    ip_right = ip_byte[32:]
    
    for i in range(16):
        temp_left = ip_left[:]
        ip_left = ip_right[:]
        key = keys[i]
        expanded_right = expand_permute(ip_right)
        xor_result = xor(expanded_right, key)
        s_box_result = s_box_permute(xor_result)
        p_result = p_permute(s_box_result)
        temp_right = xor(p_result, temp_left)
        ip_right = temp_right
    
    final_data = ip_right + ip_left
    return finally_permute(final_data)

def str_to_bt(s):
    length = len(s)
    bt = [0] * 64
    
    if length < 4:
        for i in range(length):
            k = ord(s[i])
            for j in range(16):
                pow_val = 2 ** (15 - j)
                bt[16*i+j] = (k // pow_val) % 2
        
        for p in range(length, 4):
            k = 0
            for q in range(16):
                pow_val = 2 ** (15 - q)
                bt[16*p+q] = (k // pow_val) % 2
    else:
        for i in range(4):
            k = ord(s[i])
            for j in range(16):
                pow_val = 2 ** (15 - j)
                bt[16*i+j] = (k // pow_val) % 2
    
    return bt

def bt64_to_hex(byte_data):
    hex_str = ""
    for i in range(16):
        bt = "".join(str(b) for b in byte_data[i*4:(i+1)*4])
        if bt == "0000": hex_str += "0"
        elif bt == "0001": hex_str += "1"
        elif bt == "0010": hex_str += "2"
        elif bt == "0011": hex_str += "3"
        elif bt == "0100": hex_str += "4"
        elif bt == "0101": hex_str += "5"
        elif bt == "0110": hex_str += "6"
        elif bt == "0111": hex_str += "7"
        elif bt == "1000": hex_str += "8"
        elif bt == "1001": hex_str += "9"
        elif bt == "1010": hex_str += "A"
        elif bt == "1011": hex_str += "B"
        elif bt == "1100": hex_str += "C"
        elif bt == "1101": hex_str += "D"
        elif bt == "1110": hex_str += "E"
        elif bt == "1111": hex_str += "F"
    
    return hex_str

def get_key_bytes(key):
    key_bytes = []
    length = len(key)
    iterator = length // 4
    remainder = length % 4
    
    for i in range(iterator):
        key_bytes.append(str_to_bt(key[i*4:(i+1)*4]))
    
    if remainder > 0:
        key_bytes.append(str_to_bt(key[iterator*4:]))
    
    return key_bytes

def str_enc(data, first_key, second_key, third_key):
    """
    实现JavaScript版本的strEnc加密函数
    
    Args:
        data: 要加密的数据
        first_key: 第一个密钥
        second_key: 第二个密钥
        third_key: 第三个密钥
        
    Returns:
        加密后的十六进制字符串
    """
    length = len(data)
    enc_data = ""
    
    first_key_bt = get_key_bytes(first_key) if first_key else None
    second_key_bt = get_key_bytes(second_key) if second_key else None
    third_key_bt = get_key_bytes(third_key) if third_key else None
    
    first_length = len(first_key_bt) if first_key_bt else 0
    second_length = len(second_key_bt) if second_key_bt else 0
    third_length = len(third_key_bt) if third_key_bt else 0
    
    if length > 0:
        if length < 4:
            bt = str_to_bt(data)
            
            if first_key and second_key and third_key:
                temp_bt = bt
                for x in range(first_length):
                    temp_bt = enc(temp_bt, first_key_bt[x])
                for y in range(second_length):
                    temp_bt = enc(temp_bt, second_key_bt[y])
                for z in range(third_length):
                    temp_bt = enc(temp_bt, third_key_bt[z])
                enc_byte = temp_bt
            elif first_key and second_key:
                temp_bt = bt
                for x in range(first_length):
                    temp_bt = enc(temp_bt, first_key_bt[x])
                for y in range(second_length):
                    temp_bt = enc(temp_bt, second_key_bt[y])
                enc_byte = temp_bt
            elif first_key:
                temp_bt = bt
                for x in range(first_length):
                    temp_bt = enc(temp_bt, first_key_bt[x])
                enc_byte = temp_bt
            else:
                enc_byte = bt
                
            enc_data = bt64_to_hex(enc_byte)
        else:
            iterator = length // 4
            remainder = length % 4
            
            for i in range(iterator):
                temp_data = data[i*4:(i+1)*4]
                temp_byte = str_to_bt(temp_data)
                
                if first_key and second_key and third_key:
                    temp_bt = temp_byte
                    for x in range(first_length):
                        temp_bt = enc(temp_bt, first_key_bt[x])
                    for y in range(second_length):
                        temp_bt = enc(temp_bt, second_key_bt[y])
                    for z in range(third_length):
                        temp_bt = enc(temp_bt, third_key_bt[z])
                    enc_byte = temp_bt
                elif first_key and second_key:
                    temp_bt = temp_byte
                    for x in range(first_length):
                        temp_bt = enc(temp_bt, first_key_bt[x])
                    for y in range(second_length):
                        temp_bt = enc(temp_bt, second_key_bt[y])
                    enc_byte = temp_bt
                elif first_key:
                    temp_bt = temp_byte
                    for x in range(first_length):
                        temp_bt = enc(temp_bt, first_key_bt[x])
                    enc_byte = temp_bt
                else:
                    enc_byte = temp_byte
                
                enc_data += bt64_to_hex(enc_byte)
            
            if remainder > 0:
                remain_data = data[iterator*4:]
                temp_byte = str_to_bt(remain_data)
                
                if first_key and second_key and third_key:
                    temp_bt = temp_byte
                    for x in range(first_length):
                        temp_bt = enc(temp_bt, first_key_bt[x])
                    for y in range(second_length):
                        temp_bt = enc(temp_bt, second_key_bt[y])
                    for z in range(third_length):
                        temp_bt = enc(temp_bt, third_key_bt[z])
                    enc_byte = temp_bt
                elif first_key and second_key:
                    temp_bt = temp_byte
                    for x in range(first_length):
                        temp_bt = enc(temp_bt, first_key_bt[x])
                    for y in range(second_length):
                        temp_bt = enc(temp_bt, second_key_bt[y])
                    enc_byte = temp_bt
                elif first_key:
                    temp_bt = temp_byte
                    for x in range(first_length):
                        temp_bt = enc(temp_bt, first_key_bt[x])
                    enc_byte = temp_bt
                else:
                    enc_byte = temp_byte
                
                enc_data += bt64_to_hex(enc_byte)
    
    return enc_data 