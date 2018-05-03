import os
import math
import numpy
import psycopg2
import datetime
import time
import cv2


########################################################

def create_hive_coords(input_files_location, output_location):
	# make sure input_files_location contains only directories with only csv-files and no subdirs


	if not os.path.exists(output_location):
		os.makedirs(output_location)



	####################

	# true world coordinate system corner points:

	#	t1  ------------------  t2
	#	|                        |
	#	|                        |
	#	|                        |
	#	t4  ------------------  t3


	t1 = [0.0,0.0]
	t2 = [35.2,0.0]
	t3 = [35.2,20.0]
	t4 = [0.0,20.0]

	pts_dst = numpy.array([t1,t2,t3,t4])

	# in cm

	####################



	dirnames = os.listdir(input_files_location)
	print(dirnames)
	dirnum = len(dirnames)
	i = 0

	for dirname in dirnames:

		current_path = os.path.join(input_files_location,dirname)
		cam0_text = ""
		cam1_text = ""
		files = os.listdir(current_path)
		filenum = len(files)
		print("starting directory " + str(i+1) + " of " + str(dirnum) + " which contains " + str(filenum) + " files")
		i = i+1
		
		for file in files:
			
			f = open(os.path.join(current_path,file))
			r = f.read()
			f.close()
			cam = file[14]			# get from filename
			
			####################

			r2 = r.split("\n")		# divide by line
			position = r2[0]
			time = r2[1]
			corners = r2[2]
			
			####################
			
			posdata = position.split()		# divide by whitespace
			pos = numpy.array([float(posdata[0])*4,float(posdata[1])*4,1.0])		# position of dance in WDD (value was downscaled to 160x120 resolution; *4 gets it back to 640x480)
			
			###
			
			timedata = time.split()
			time = timedata[0]
			
			###
			
			cornerdata = corners.split()
			p1 = [float(cornerdata[0]),float(cornerdata[1])]
			p2 = [float(cornerdata[2]),float(cornerdata[3])]
			p3 = [float(cornerdata[4]),float(cornerdata[5])]
			p4 = [float(cornerdata[6]),float(cornerdata[7])]
			
			pts_src = numpy.array([p1,p2,p3,p4])
			
			#	p1  ------------------  p2
			#	|                        |
			#	|                        |
			#	|                        |
			#	p4  ------------------  p3
			
			
			####################
			
			h, status = cv2.findHomography(pts_src, pts_dst)			# h is homography matrix
			calc = numpy.dot(h,pos)										# transforming the WDD dance position
			world_coord_pos = [round(calc[0],4),round(calc[1],4)]
			
			if cam == '0':
				cam0_text = cam0_text + time + " " + str(world_coord_pos[0]) + " " + str(world_coord_pos[1]) + "\n"
			elif cam == '1':
				cam1_text = cam1_text + time + " " + str(world_coord_pos[0]) + " " + str(world_coord_pos[1]) + "\n"
			else:
				print(error)
		
		f0 = open(os.path.join(output_location,dirname + " cam0.txt"),'w')
		f0.write(cam0_text)
		f0.close()
		
		f1 = open(os.path.join(output_location,dirname + " cam1.txt"),'w')
		f1.write(cam1_text)
		f1.close()
		
	print("completed!")
########################################################


### just a help function
def save_results(table,row):
	table_col_names = ("timestamp","frame_id","detection_idx","track_id","x_pos","y_pos","orientation","x_pos_hive","y_pos_hive","orientation_hive","bee_id","bee_id_confidence","cam_id")
	i = 0
	rowdict = {}
	for item in row:
		rowdict[table_col_names[i]] = item
		i = i + 1
	table.append(rowdict)
	
### just a help function
def get_delta_angle(target_angle,source_angle):														# gets signed difference
	return(min(source_angle - target_angle, source_angle - target_angle + 2 * math.pi, source_angle - target_angle - 2 * math.pi, key=abs))
	
### just a help function
def dist(p1,p2):
	return(math.hypot(p2[0]-p1[0],p2[1]-p1[1]))

### just a help function
def get_normalized_distance(p_list):
	if len(p_list) > 1:
		total_dist = 0.0
		prev_val = p_list[0]
		for cur_val in p_list[1:]:
			total_dist = total_dist + dist(prev_val,cur_val)
			prev_val = cur_val
		#print(total_dist)
		return(total_dist / float(len(p_list)-1))
	else:
		return(0.0)
		
### just a help function
# scores high, if bee is generally turning much
def get_orientation_activity(ori_list):
	if len(ori_list) > 1:
		total_delta = 0.0
		prev_val = ori_list[0]
		for cur_val in ori_list[1:]:
			total_delta = total_delta + abs(get_delta_angle(prev_val,cur_val))
			prev_val = cur_val
		return(total_delta / float(len(ori_list)-1))		# average_turning_angle
	else:
		return(0.0)
	
### just a help function
def get_low_change_in_position(p_list):
	if len(p_list) > 0:
		total_x = 0
		total_y = 0
		point_number = len(p_list)
		for p in p_list:
			total_x = total_x + p[0]
			total_y = total_y + p[1]
		hover = [int(round(total_x / float(point_number))) , int(round(total_y / float(point_number)))]
		#print(hover)
		total_hover_dist = 0.0
		for p in p_list:
			total_hover_dist = total_hover_dist + dist(p,hover)
		return(total_hover_dist / float(point_number))
	else:
		return(0.733)
	
### just a help function
# this scores high, if the bee is not changing her orientation until a certain point ( waggle run orientation )
def get_common_orientation_point(ori_list):
	if len(ori_list) > 2:
		turning_points = []
		first_val = ori_list[0]
		prev_val = ori_list[1]
		prev_delta = get_delta_angle(first_val,prev_val)
		prev_is_positive = prev_delta > 0
		for cur_val in ori_list[2:]:
			cur_delta = get_delta_angle(prev_val,cur_val)
			cur_is_positive = cur_delta > 0
			if prev_is_positive != cur_is_positive:	# wechsel im vorzeichen
				turning_points.append(prev_val)
			prev_val = cur_val
			prev_is_positive = cur_is_positive
		#print(turning_points)
		number_turning_points = len(turning_points)
		turning_point_rate = 1.0
		if number_turning_points != 0:
			turning_point_rate = len(ori_list) / float(number_turning_points)		# if high, then maybe signal
		else:
			number_turning_points = 1
		#print(turning_point_rate)
		best_numbers_of_points_in_tolerance_area = 0
		for i in range(len(turning_points)):
			numbers_of_points_in_tolerance_area = 0
			for j in range(len(turning_points)):
				abs_delta  = abs(get_delta_angle(turning_points[i],turning_points[j]))
				if abs_delta < 0.5:
					numbers_of_points_in_tolerance_area = numbers_of_points_in_tolerance_area + 1
			if numbers_of_points_in_tolerance_area > best_numbers_of_points_in_tolerance_area:
				best_numbers_of_points_in_tolerance_area = numbers_of_points_in_tolerance_area
		#print(best_numbers_of_points_in_tolerance_area)
		common_orientation_point_rate = best_numbers_of_points_in_tolerance_area / float(number_turning_points)		# the higher, the greater the signal
		return(common_orientation_point_rate * turning_point_rate)			
	else:
		return(0.0)
			
### just a help function
def get_full_circle_detections(ori_list):
	if len(ori_list) > 2:
		first_val = ori_list[0]
		prev_val = ori_list[1]
		prev_delta = get_delta_angle(first_val,prev_val)
		prev_is_positive = prev_delta > 0
		total_circle_rot = prev_delta
		circles = []
		for cur_val in ori_list[2:]:
			cur_delta = get_delta_angle(prev_val,cur_val)
			cur_is_positive = cur_delta > 0
			if prev_is_positive == cur_is_positive:
				total_circle_rot = total_circle_rot + cur_delta
			else:
				if abs(total_circle_rot) > 5.5:						# collecting all rotations which are a bit less than 2 * pi or larger
					circles.append(total_circle_rot)
				total_circle_rot = cur_delta
			prev_delta = cur_delta
			prev_is_positive = cur_is_positive
			prev_val = cur_val
		#print(circles)
		pos_circles = 0
		neg_circles = 0
		alternating = 0
		if len(circles) > 0:										# evaluating circles, wether they have alternating signs (return runs) , or at least have different signs, preferably about the same amount
			prev_sign_pos = circles[0] > 0
			if prev_sign_pos:
				pos_circles = pos_circles + 1
			else:
				neg_circles = neg_circles + 1
			for circle in circles[1:]:
				cur_sign_pos = circle > 0
				if cur_sign_pos:
					pos_circles = pos_circles + 1
				else:
					neg_circles = neg_circles + 1
				if prev_sign_pos != cur_sign_pos:
					alternating = alternating + 1
				prev_sign_pos = cur_sign_pos
			#print([pos_circles,neg_circles,alternating])
			diff_in_amount = abs(pos_circles - neg_circles)
			if diff_in_amount == 0:
				diff_in_amount = 1
			multiplier = 10.0 / float(diff_in_amount)
			score = (pos_circles + neg_circles) * multiplier + alternating * 10.0
			#print(score)
			return(score / float(len(ori_list)))
		else:
			return(0.0)
	else:
		return(0.0)
		
### just a help function
def final_scoring(avg_speed,avg_rot,c_ori_p,low_change_pos,full_c):
	influence = [0.0, 0.0, 0.0, 0.0, 0.0]
	
	# avg_speed is around 0.2 cm/frame for non dancers (-1.0)  and about 0.6 cm/frame or more for dancers (1.0)
	if avg_speed < 0.2:		#30
		influence[0] = -1.0
	elif avg_speed < 0.233:		#35
		influence[0] = -0.99
	elif avg_speed < 0.266:		#40
		influence[0] = -0.98
	elif avg_speed < 0.3:		#45
		influence[0] = -0.96
	elif avg_speed < 0.333:		#50
		influence[0] = -0.90
	elif avg_speed < 0.366:		#55
		influence[0] = -0.3
	elif avg_speed < 0.4:		#60
		influence[0] = -0.1
	elif avg_speed < 0.433:		#65
		influence[0] = 0.1
	elif avg_speed < 0.466:		#70
		influence[0] = 0.6
	elif avg_speed < 0.5:		#75
		influence[0] = 0.9
	elif avg_speed < 0.533:		#80
		influence[0] = 0.96
	elif avg_speed < 0.566:		#85
		influence[0] = 0.98
	elif avg_speed < 0.6:		#90
		influence[0] = 0.99
	else:
		influence[0] = 1.0
		
	# avg_rot is around 0.3 for non dancers (-1.0)  and about 1.1 or more for dancers (1.0)
	if avg_rot < 0.3:
		influence[1] = -1.0
	elif avg_rot < 0.4:
		influence[1] = -0.99
	elif avg_rot < 0.5:
		influence[1] = -0.95
	elif avg_rot < 0.6:
		influence[1] = -0.6
	elif avg_rot < 0.7:
		influence[1] = -0.2
	elif avg_rot < 0.8:
		influence[1] = 0.2
	elif avg_rot < 0.9:
		influence[1] = 0.6
	elif avg_rot < 1.0:
		influence[1] = 0.95
	elif avg_rot < 1.1:
		influence[1] = 0.99
	else:
		influence[1] = 1.0
		
	# only sometimes is above 2.0 ish for dancers, but not necessarily
	if c_ori_p < 1.5:
		influence[2] = 0.0
	elif c_ori_p < 1.8:
		influence[2] = 0.3
	elif c_ori_p < 2.0:
		influence[2] = 0.7
	else:
		influence[2] = 0.9
		
	# dancers usually are around 0.733 to 0.866 cm, but non-dancers can be too. Non-dancers are between 0.266 to 2.0+ cm.
	if low_change_pos < 0.466:		#70
		influence[3] = -0.9
	elif low_change_pos < 0.533:		#80
		influence[3] = -0.7
	elif low_change_pos < 0.6:		#90
		influence[3] = -0.5
	elif low_change_pos < 0.666:		#100
		influence[3] = -0.2
	elif low_change_pos < 0.933:		#140
		influence[3] = 0.0
	elif low_change_pos < 1.0:		#150
		influence[3] = -0.1
	elif low_change_pos < 1.066:		#160
		influence[3] = -0.3
	elif low_change_pos < 1.2:		#180
		influence[3] = -0.6
	elif low_change_pos < 1.333:		#200
		influence[3] = -0.8
	else:
		influence[3] = -0.9
		
	# dancers should have a number other than 0.0 ;   many non-dancers have 0.0, rarely have higher numbers ;  very high numbers should clearly be dancers
	if full_c == 0.0:
		influence[4] = -1.0
	elif full_c < 0.5:
		influence[4] = 0.4
	elif full_c < 1.0:
		influence[4] = 0.6
	elif full_c < 1.5:
		influence[4] = 0.8
	elif full_c < 2.0:
		influence[4] = 0.9
	else:
		influence[4] = 1.0
	
	
	score = 0.0
	for val in influence:
		score = score + val

	#print(influence)
	return(score/4.0)
	
	
# find_dancers:
##### wdd_hive_coords_folder is expected to contain files with a name like "20160729 cam1.txt" , "20160809 cam0.txt"  etc.
##### wdd_hive_coords_files are expected to look like this:
#								#00:00:36:594 8.4858 12.0572
#								#00:02:38:070 28.3649 12.7785
#								#00:03:45:422 30.4568 16.9055
#								#00:04:08:898 26.4196 15.2199	etc.
##### date should simply be a tuple like this:		(2016,9,15)   etc. ;  the purpose of this is to split work, as everything together is very time consuming
##### results_folder is were you want the result files to be saved
def find_dancers(wdd_hive_coords_folder,date,results_folder):
	query = """
	SELECT * FROM bb_detections A
	WHERE
		A.cam_id = %s
		AND A.timestamp >= (TIMESTAMP WITH TIME ZONE 'epoch' + %s * INTERVAL '1 second')
		AND A.timestamp <= (TIMESTAMP WITH TIME ZONE 'epoch' + %s * INTERVAL '1 second')
		AND A.x_pos_hive >= %s
		AND A.x_pos_hive <= %s
		AND A.y_pos_hive >= %s
		AND A.y_pos_hive <= %s
	"""

	query2 = """
	SELECT * FROM bb_detections A
	WHERE
		A.track_id = %s
		AND A.cam_id = %s
		AND A.timestamp >= (TIMESTAMP WITH TIME ZONE 'epoch' + %s * INTERVAL '1 second')
		AND A.timestamp <= (TIMESTAMP WITH TIME ZONE 'epoch' + %s * INTERVAL '1 second')
	"""
	
	wdd_file_path =  wdd_hive_coords_folder
	target_path =  results_folder
	if not os.path.exists(target_path):
		os.mkdir(target_path)
	
	wdd_files = []
	for dirpath, dirnames, filenames in os.walk(wdd_file_path):
		for filename in filenames:
			wdd_files.append(os.path.join(dirpath,filename))
			
	year,month,day = date
	s_month = str(month)
	if month < 10:
		s_month = "0" + s_month
	s_day = str(day)
	if day < 10:
		s_day = "0" + s_day
		
	file_cam0 = os.path.join(wdd_file_path, str(year) + s_month + s_day + " cam0.txt")
	file_cam1 = os.path.join(wdd_file_path,str(year) + s_month + s_day + " cam1.txt")
		
	if file_cam0 in wdd_files and file_cam1 in wdd_files:
		for file in [file_cam0,file_cam1]:
			f_wdd = open(file,'r')
			text_wdd = f_wdd.read()
			f_wdd.close()
			result_text_cam_0 = ''
			result_text_cam_1 = ''
			time_tolerance = 1.0	#seconds
			area_tolerance = 1.0	#centimetres
			for detection in text_wdd.strip().split("\n"):
				det_values = detection.split()
				wdd_time = det_values[0]
				x_wdd = float(det_values[1])
				y_wdd = float(det_values[2])
				timepoints = wdd_time.split(":")
				hour,minute,second,microsecond = int(timepoints[0]),int(timepoints[1]),int(timepoints[2]),int(timepoints[3])
				timestamp_wdd = datetime.datetime(year,month,day,hour,minute,second,microsecond)
				wdd_epoch = time.mktime(timestamp_wdd.timetuple())
				cam_id = 0
				if x_wdd > 17.6 and file == file_cam0:
					cam_id = 1
				elif x_wdd < 17.6 and file == file_cam1:
					cam_id = 2
				elif x_wdd > 17.6 and file == file_cam1:
					cam_id = 3
				results = []
				# collecting all tracks in the area of detection
				with psycopg2.connect("dbname='beesbook' user='reader' host='localhost' password='reader'", application_name="wdd detection") as db:
					cur = db.cursor()
					cur.execute(query,(cam_id, wdd_epoch -time_tolerance,wdd_epoch + time_tolerance,x_wdd - area_tolerance ,x_wdd + area_tolerance, y_wdd -area_tolerance, y_wdd + area_tolerance))
					for row in cur:
						save_results(results,row)
						
				bees = []
				for line in results:
					if line["track_id"] in bees:
						pass
					else:
						bees.append(line["track_id"])
						# print(line["track_id"])
						# print(line["bee_id"])
						# print("------")
				
				print(len(bees))
				
				bee_scores = []
				for bee in bees:
					# evaluating found tracks
					results2 = []
					with psycopg2.connect("dbname='beesbook' user='reader' host='localhost' password='reader'", application_name="track detection " + str(bee)) as db:
						cur = db.cursor()
						cur.execute(query2,(bee, cam_id, wdd_epoch, wdd_epoch + 20.0))			# 20 second tracks
						for row in cur:
							save_results(results2,row)
							
						point_list = []
						orientation_list = []
						#print(results2[0]["bee_id"])
						bee_id = -1
						bee_x_pos = -1
						bee_y_pos = -1
						try:
							bee_id = results2[0]["bee_id"]
							bee_x_pos = results2[0]["x_pos"]
							bee_y_pos = results2[0]["y_pos"]
						except:
							pass
						for line in results2:
							point_list.append([line["x_pos"],line["y_pos"]])
							orientation_list.append(line["orientation"])
							
						normalized_distance = get_normalized_distance(point_list)
						orientation_activity = get_orientation_activity(orientation_list)
						common_orientation_point = get_common_orientation_point(orientation_list)
						low_change_in_position = get_low_change_in_position(point_list)
						full_circle_detections = get_full_circle_detections(orientation_list)
						final_score = final_scoring(normalized_distance,orientation_activity,common_orientation_point,low_change_in_position,full_circle_detections)
						bee_scores.append([bee_id,final_score,bee_x_pos,bee_y_pos])
						
				sorted_bee_scores = sorted(bee_scores, key = lambda x: x[1], reverse=True)
				dancers = []
				non_dancers = []
				for bee in sorted_bee_scores:
					if bee[1] >= 0.0:
						dancers.append(bee)
					else:
						non_dancers.append(bee)
						
				# adding results to text
				if file == file_cam0:
					result_text_cam_0 = result_text_cam_0 + str(datetime.datetime.utcfromtimestamp(wdd_epoch)) + ":" + str(microsecond) + " (utc)  " + str(x_wdd) + " " + str(y_wdd) + "\n"
					first_dancer = True
					for dancer in dancers:
						if first_dancer:
							result_text_cam_0 = result_text_cam_0 + "\tDancers:\t" + str(dancer[0]) + "\t" + str(dancer[1]) + "\t" + str(dancer[2]) + " " + str(dancer[3]) + "\n"
							first_dancer = False
						else:
							result_text_cam_0 = result_text_cam_0 + "\t\t\t" + str(dancer[0]) + "\t" + str(dancer[1]) + "\t" + str(dancer[2]) + " " + str(dancer[3]) + "\n"
					first_non_dancer = True
					for non_dancer in non_dancers:
						if first_non_dancer:
							result_text_cam_0 = result_text_cam_0 + "\tNon-Dancers:\t" + str(non_dancer[0]) + "\t" + str(non_dancer[1]) + "\t" + str(non_dancer[2]) + " " + str(non_dancer[3]) + "\n"
							first_non_dancer = False
						else:
							result_text_cam_0 = result_text_cam_0 + "\t\t\t" + str(non_dancer[0]) + "\t" + str(non_dancer[1]) + "\t" + str(non_dancer[2]) + " " + str(non_dancer[3]) + "\n"
				else:
					result_text_cam_1 = result_text_cam_1 + str(datetime.datetime.utcfromtimestamp(wdd_epoch)) + ":" + str(microsecond) + " (utc)  " + str(x_wdd) + " " + str(y_wdd) + "\n"
					first_dancer = True
					for dancer in dancers:
						if first_dancer:
							result_text_cam_1 = result_text_cam_1 + "\tDancers:\t" + str(dancer[0]) + "\t" + str(dancer[1]) + "\t" + str(dancer[2]) + " " + str(dancer[3]) + "\n"
							first_dancer = False
						else:
							result_text_cam_1 = result_text_cam_1 + "\t\t\t" + str(dancer[0]) + "\t" + str(dancer[1]) + "\t" + str(dancer[2]) + " " + str(dancer[3]) + "\n"
					first_non_dancer = True
					for non_dancer in non_dancers:
						if first_non_dancer:
							result_text_cam_1 = result_text_cam_1 + "\tNon-Dancers:\t" + str(non_dancer[0]) + "\t" + str(non_dancer[1]) + "\t" + str(non_dancer[2]) + " " + str(non_dancer[3]) + "\n"
							first_non_dancer = False
						else:
							result_text_cam_1 = result_text_cam_1 + "\t\t\t" + str(non_dancer[0]) + "\t" + str(non_dancer[1]) + "\t" + str(non_dancer[2]) + " " + str(non_dancer[3]) + "\n"
							
							
			fr1 = open(target_path + wdd_file_path, str(year) + s_month + s_day + "cam0 dancers.txt",'w')
			fr1.write(result_text_cam_0)
			fr1.close()
			fr2 = open(target_path + wdd_file_path, str(year) + s_month + s_day + "cam1 dancers.txt",'w')
			fr2.write(result_text_cam_1)
			fr2.close()
		

		
		
		
		
		
		
# this_files_path_and_filename = os.path.realpath(__file__)
# this_files_filename = this_files_path_and_filename.split(os.sep)[-1]
# this_files_path = this_files_path_and_filename[:-(len(this_files_filename))]

# wddfilepath =  this_files_path + "world-coordinates-positions" + os.sep
# targetpath = this_files_path + "hive-test" + os.sep
# find_dancers(wddfilepath,(2016,8,7),targetpath)
	
