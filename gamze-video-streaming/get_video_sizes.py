import os


TOTAL_VIDEO_CHUNCK = 49
BITRATE_LEVELS = 6
VIDEO_PATH = 'video_server/testVideo/'
VIDEO_FOLDER = 'video'

# assume videos are in ../video_servers/video[1, 2, 3, 4, 5]
# the quality at video5 is the lowest and video1 is the highest


for bitrate in xrange(BITRATE_LEVELS):
	with open('video_sizes/video_size_' + str(bitrate), 'wb') as f:
		print('\n')
		print(bitrate)
		for chunk_num in range(1, TOTAL_VIDEO_CHUNCK+1):
			video_chunk_path = VIDEO_PATH + \
							   VIDEO_FOLDER + \
							   str(BITRATE_LEVELS - bitrate) + \
							   '/' + \
							   str(chunk_num) + \
							   '.m4s'
			chunk_size = os.path.getsize(video_chunk_path)
			print(str(chunk_size * 8 / 4))
			f.write(str(chunk_size) + '\n')
