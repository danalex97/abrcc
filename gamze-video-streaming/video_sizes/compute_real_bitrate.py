import sys

CHUNK_LENGTH = 3.9388 # chunk is 3.9 seconds (video length: 3:13, number of chunks: 49)
BITS_PER_BYTE = 8
INPUT_PREFIX = 'video_size_'
OUTPUT_PREFIX = 'bitrate_'

input_path = 'video_size_5'
output_path = 'bitrate_5'


for i in range(6):
    input_path = INPUT_PREFIX + str(i)
    output_path = OUTPUT_PREFIX + str(i)
    
    total_size = 0
    total_duration = 193
    
    with open(input_path, 'r') as input_file, open(output_path, 'w+') as output_file:
        for line in input_file:
            chunk_size = (float)(line) # bytes
            true_bitrate = chunk_size / CHUNK_LENGTH * BITS_PER_BYTE # bps
            output_file.write(str(true_bitrate) + '\n')
            
            total_size += chunk_size
    
    print('video ' + str(i) + ' | average bitrate: ' + str(total_size / total_duration * BITS_PER_BYTE) +'\n\n')
    print(str(total_size))
