#This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

#This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

#You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>. 

import re
from PIL import Image, ImageDraw
import math
import argparse
import sys
import os
import tkinter as tk
from tkinter.filedialog import askopenfilename
from tkinter.font import Font

version = "v5.35"

def quit():
  sys.exit()

def extract_lines_from_file(in_file):
  file_rows = []
  row_open = False
  for row in in_file:
    row_idx = 0  
    st_subrow_idx = 0
    while True:
      #look for starting symbol
      if row_open == False:
        st_subrow_idx = row.find('<', row_idx)
        if st_subrow_idx == -1:
          break
      
      #if we are here row is started
      en_subrow_idx = row.find('>', st_subrow_idx)
      if en_subrow_idx == -1:  #no ending symbol
        if row_open == False:  #if first subrow
          file_rows.append(row)
          row_open = True
          break
        else:                   #not first subrow
          file_rows[-1] = file_rows[-1] + row
          break  
      
      #if we are here ending symbol was found
      if row_open == True:
        file_rows[-1] = file_rows[-1] + row
        row_open = False
        break
      
      #if we are here we have to deal with subrow
      new_row = row[st_subrow_idx:en_subrow_idx+1]
      if(new_row.find("</text>") != -1):
        file_rows[-1] += row[row_idx:en_subrow_idx+1]
      else:
        file_rows.append(new_row)
      
      row_open = False
      row_idx = en_subrow_idx+1
  
  return file_rows

def find_layer_limits(layer_name, rows):
  start_idx = 0
  for row in rows:
    start_idx = start_idx+1
    if layer_name in row:
      break
  
  if start_idx == len(rows):
    print('\nLayer ', layer_name, ' not found! Try another file or fix it :)')
    text_box.insert("end", "\n\nLayer " + layer_name + " not found! Try another file or fix it :)")
    return '_', '_', False

  end_idx = 0
  num_of_final_char = 1
  for row_idx in range(start_idx, len(rows)):
    if "<g" in rows[row_idx]:
      num_of_final_char += 1
    if "</g>" in rows[row_idx]:
      num_of_final_char -= 1
      if num_of_final_char == 0:
        end_idx = row_idx
        break
  
  return start_idx, end_idx, True


#reads input row containing "line" info -> row has to be of type """<line class="st1" x1="181.2" y1="404.9" x2="182.2" y2="406.1"/>"""
def read_line(row):
  x1 = float(re.search('x1="(.+?)"', row).group(1))
  y1 = float(re.search('y1="(.+?)"', row).group(1))
  x2 = float(re.search('x2="(.+?)"', row).group(1))
  y2 = float(re.search('y2="(.+?)"', row).group(1))
  
  if x1 > x2:
    return x2, y2, x1, y1
  else:
    return x1, y1, x2, y2

#reads input row containing "polyline" info -> row has to be of type """<polyline class="st1" points="172.7,402.8 174.9,404.4 176.9,406 178.6,406.8 180.4,407.8 	"/>"""
def read_polyline(row):
  start_ind = row.find('points="')+8
  end_of_line = False
  points = []
  
  # old illustrator (2018, 2019)
  if(row[start_ind:].find(',') != -1):
    while end_of_line == False:
      end_ind = row[start_ind:].find(' ')
      x = float(re.search('(.*),', row[start_ind:start_ind+end_ind]).group(1))
      y = float(re.search(',(.*)', row[start_ind:start_ind+end_ind]).group(1))    
      points.append([x,y])
      if row[start_ind+end_ind+1:].find(',') == -1:
        end_of_line = True
      else:
        start_ind = start_ind+end_ind+1
  
  # new illustrator (2020)
  else:
    while end_of_line == False:
      end_ind = row.find(' ', start_ind)
      x = float(row[start_ind:end_ind])
      new_end_ind = row.find(' ', end_ind+1)
      if(new_end_ind == -1):
        new_end_ind = row.find('"', end_ind+1)
        end_of_line = True
      else:
        start_ind = new_end_ind+1
      y = float(row[end_ind+1:new_end_ind])
      points.append([x,y])
      
  return points
  
#reads row containing "polygon" info -> row is of polyline style but extremas points are not equal -> assuming the presence of closing segment
def read_polygon(row):
  #legge polyline..
  polyline_points = read_polyline(row)
  
  #e la chiude! (solo se non lo è già!)
  if(polyline_points[0] != polyline_points[-1]):
    polyline_points.append(polyline_points[0])
      
  return polyline_points

#reads row containg "rect" info and disassembling into 4 lines --> row has to be of type <rect x="473.9" y="273.7" class="st11" width="32.1" height="18.5"/>  
def read_rect(row):
  x = float(re.search('x="(.+?)"', row).group(1))
  y = float(re.search('y="(.+?)"', row).group(1))
  width = float(re.search('width="(.+?)"', row).group(1))
  height = float(re.search('height="(.+?)"', row).group(1))
  
  line_1 =       x,        y, x+width,        y
  line_2 = x+width,        y, x+width, y+height
  line_3 = x+width, y+height,       x, y+height
  line_4 =       x, y+height,       x,        y
  
  return line_1, line_2, line_3, line_4

#reads row containing "circle" info -> row has to be of type """<circle class="st4" cx="488.1" cy="297.6" r="46.6"/>"""
def read_circle(row):
  cx = float(re.search('cx="(.+?)"', row).group(1))
  cy = float(re.search('cy="(.+?)"', row).group(1))
  r = float(re.search('r="(.+?)"', row).group(1))
  return cx, cy, r

# reads row containing scale line length -> row has to be of type """<text transform="matrix(1 0 0 1 684.1914 572.5094)" class="st7 st8">20</text>"""
def read_scale_length(row):
  start_backsearch_ind = row.find('</text>')
  end_ind_found = False
  start_ind_found = False
  for ind in range(start_backsearch_ind, 0, -1):
    if not end_ind_found:
      if row[ind].isdigit() == True:
        end_ind = ind
        end_ind_found = True
      continue
        
    if row[ind].isdigit() == False:
      start_ind = ind+1
      break
  
  return int(row[start_ind:end_ind+1])

# calculates scale factor
def calculate_scale_factor(file_rows, start_scale_rows, end_scale_rows):
  scale_line = []
  for r_idx in range(start_scale_rows, end_scale_rows):
    if file_rows[r_idx].find("<line") != -1:
      scale_line.append(read_line(file_rows[r_idx]))
    if file_rows[r_idx].find("text") != -1:
      scale_length_metres = read_scale_length(file_rows[r_idx])

  scale_length_pixels = math.sqrt(pow(scale_line[0][2] - scale_line[0][0],2)+pow(scale_line[0][3] - scale_line[0][1],2))
  scale_factor = scale_length_metres / scale_length_pixels
  print('\nScale factor: ',  "{:.3f}".format(scale_factor), '  Meters: ', "{:.3f}".format(scale_length_metres), "  Pixels: ", "{:.3f}".format(scale_length_pixels))
  text_box.insert("end", "\n\nScale factor: " + "{:.3f}".format(scale_factor) + "  Meters: " + "{:.3f}".format(scale_length_metres) + "  Pixels: " + "{:.3f}".format(scale_length_pixels))
  return scale_factor

# finds intersection point between two lines (assuming lines infinite)
def find_intersection_point(line_1, line_2):
  if (line_1[2]-line_1[0]) != 0 and (line_2[2]-line_2[0]) != 0:
    m1 = (line_1[3]-line_1[1]) / (line_1[2]-line_1[0])
    q1 = line_1[1] - m1*line_1[0]
  
    m2 = (line_2[3]-line_2[1]) / (line_2[2]-line_2[0])
    q2 = line_2[1] - m2*line_2[0]
    
    #parallel lines
    if (m1 == m2):
      return 0, 0
      
    q2 = line_2[1] - m2*line_2[0]
    x_int = (q2-q1) / (m1-m2)
    y_int = m1*x_int + q1
  
  else:
    if (line_1[2]-line_1[0]) == 0:
      oriz  = line_1
      other = line_2
    else:
      oriz  = line_2
      other = line_1
    
    #horizontal and parallel  
    if (other[2]-other[0]) == 0:
      return 0, 0
      
    m_oth = (other[3]-other[1]) / (other[2]-other[0]) 
    q_oth = other[1] - m_oth*other[0] 
    
    x_int = oriz[0]
    y_int = m_oth*x_int + q_oth

  return x_int, y_int

# check if given intersections lies over given line segments
def intersection_is_valid(x_int, y_int, line_1, line_2):
  #check line 1
  v_int_x = x_int - line_1[0]
  v_int_y = y_int - line_1[1]
  v_lin_x = line_1[2] - line_1[0]
  v_lin_y = line_1[3] - line_1[1]
  
  if(v_lin_x == 0) and (v_lin_y == 0):
    return False
    
  proj_r_1 = ((v_int_x*v_lin_x) + (v_int_y*v_lin_y))/(pow(v_lin_x,2) + pow(v_lin_y,2))
  
  #check line 2
  v_int_x = x_int - line_2[0]
  v_int_y = y_int - line_2[1]
  v_lin_x = line_2[2] - line_2[0]
  v_lin_y = line_2[3] - line_2[1]
  
  if(v_lin_x == 0) and (v_lin_y == 0):
    return False
    
  proj_r_2 = ((v_int_x*v_lin_x) + (v_int_y*v_lin_y))/(pow(v_lin_x,2) + pow(v_lin_y,2))
  
  if (proj_r_1 > 0.0) and (proj_r_2 > 0.0) and (proj_r_1 < 1.0) and (proj_r_2 < 1.0):
    return True
  else:
    return False

# projects the given point over the given line
def line_projection(p_x, p_y, line):
  v_p_x = p_x - line[0]
  v_p_y = p_y - line[1]
  v_lin_x = line[2] - line[0]
  v_lin_y = line[3] - line[1]
  proj = ((v_p_x*v_lin_x) + (v_p_y*v_lin_y))/math.sqrt((pow(v_lin_x,2) + pow(v_lin_y,2)))
  return proj    

# brings angle inside the [-pi, pi] range
def angle_wrapping(angle):
  while (angle < 0.0):
    angle += math.pi
  while (angle > math.pi):
    angle -= math.pi
  return angle

# converts angle from rad to deg
def rad_to_deg(angle_rad):
  angle_deg = angle_rad * 180.0 / math.pi
  return angle_deg

# calculates the direction of the given line
def line_direction(line):
  direction = math.atan2((line[3]-line[1]), (line[2]-line[0]))
  return angle_wrapping(direction)

def get_side(a, b):
  x = a[0]*b[1]-a[1]*b[0]
  if x < 0:
      return -1
  elif x > 0: 
      return +1
  else:
      return None
  
def is_inside_convex_polygon(pt, polygon):
  previous_side = None
  for side in polygon:
    side_vec = [side[2]-side[0], side[3]-side[1]]  
    pt_vec   = [pt[0]-side[0], pt[1]-side[1]]
    current_side = get_side(side_vec, pt_vec)
  
    if current_side is None:
      return False                        #outside or over an edge
    elif previous_side is None:           #first segment
      previous_side = current_side
    elif previous_side != current_side:
      return False
  return True
  
def is_inside_circle(pt, circle):
  
  pt_center_dist = math.sqrt(pow(pt[0]-circle[0],2) + pow(pt[1]-circle[1],2))

  return circle[2] > pt_center_dist
  
def compute_inside_fractures_in_polygon(fractures_lines, fractures_polylines, polygon):
  #check if lines are inside the polygon
  inside_lines = []
  num_additional_fractures = 0  #used to avoid to count polylines more than once
  
  for line in fractures_lines:
    start_inside = is_inside_convex_polygon([line[0],line[1]], polygon)
    end_inside   = is_inside_convex_polygon([line[2],line[3]], polygon)
    
    if(start_inside and end_inside):  #the whole line is contained
      inside_lines.append(line)

    elif(not start_inside and not end_inside):  #extremes are not inside, but we have to check if the line still cross the whole area
      start_found = False
      new_start = []
      new_end   = []
      for side in polygon:
        int_x, int_y = find_intersection_point(line, side)
        if intersection_is_valid(int_x, int_y, line, side):
          if not start_found:
            new_start = [int_x, int_y]
            start_found = True
          else:
            new_end = [int_x, int_y]
            break
        
      if start_found:                         #means that line crosses the polygon
        inside_lines.append([new_start[0], new_start[1], new_end[0], new_end[1]])

    else:
      new_start = []
      if(start_inside):
        new_start = [line[0], line[1]]
      else:
        new_start = [line[2], line[3]]
      
      for side in polygon:
        int_x, int_y = find_intersection_point(line, side)
        if intersection_is_valid(int_x, int_y, line, side):
          inside_lines.append([new_start[0], new_start[1], int_x, int_y])
          break

  #check if polylines are inside the polygon
  inside_polylines = []
  for poly in fractures_polylines:
    shrinked_poly = []
    started = False
    num_sub_polylines = 0
  
    #check if starts from inside the polygon
    start_inside = is_inside_convex_polygon([poly[0][0],poly[0][1]], polygon)
    if start_inside:
      shrinked_poly.append(poly[0])
      started = True
    
    for polypt_ind in range(1, len(poly)):
      poly_seg = poly[polypt_ind-1][0], poly[polypt_ind-1][1], poly[polypt_ind][0], poly[polypt_ind][1]
      poly_seg_intersect = False
      for lato in polygon:
        int_x, int_y = find_intersection_point(poly_seg, lato)
        if intersection_is_valid(int_x, int_y, poly_seg, lato):
          shrinked_poly.append([int_x, int_y])
          poly_seg_intersect = True
          if started:
            inside_polylines.append(shrinked_poly)
            num_sub_polylines = num_sub_polylines + 1
            shrinked_poly = []
            started = False
          else:
            started = True
      
      if poly_seg_intersect == True and started == True:
        shrinked_poly.append(poly[polypt_ind])
       
      if poly_seg_intersect == False and started == True:
        shrinked_poly.append(poly[polypt_ind]) 
    
    if started == True:   #we are ending inside polygon
      inside_polylines.append(shrinked_poly)
      num_sub_polylines = num_sub_polylines + 1
    
    if num_sub_polylines > 1:
        num_additional_fractures = num_additional_fractures + num_sub_polylines - 1
      
  print('\nNumber of internal fractures found: ',  len(inside_lines)+len(inside_polylines))
  text_box.insert("end", "\n\nNumber of internal fractures found: " + str(len(inside_lines)+len(inside_polylines)))
  
  return inside_lines, inside_polylines, num_additional_fractures

# we assume that intersection exists,  since we have controlled before that one points lies inside and the other outside
def circle_segment_intersection(circle, seg):
  seg_vec = [seg[2]-seg[0], seg[3]-seg[1]]  #d
  cen_seg_vec = [seg[0]-circle[0], seg[1]-circle[1]] #f
  
  a = seg_vec[0]*seg_vec[0] + seg_vec[1]*seg_vec[1]
  b = 2.0 * (cen_seg_vec[0]*seg_vec[0] + cen_seg_vec[1]*seg_vec[1])
  c = cen_seg_vec[0]*cen_seg_vec[0] + cen_seg_vec[1]*cen_seg_vec[1] - circle[2]*circle[2]

  discriminant = b*b-4.0*a*c;
  if discriminant < 0:    #no intersections
    return [[0,0],[0,0]], 0

  discriminant = math.sqrt( discriminant )
  t1 = (-b - discriminant)/(2*a);
  t2 = (-b + discriminant)/(2*a);
  
  inters = [[0,0], [0,0]]
  num_inters = 0
  
  if( t1 >= 0 and t1 <= 1 ):
    inters[num_inters] = [seg[0]+t1*seg_vec[0], seg[1]+t1*seg_vec[1]]
    num_inters = num_inters +1
  
  if( t2 >= 0 and t2 <= 1 ):
    inters[num_inters] = [seg[0]+t2*seg_vec[0], seg[1]+t2*seg_vec[1]]
    num_inters = num_inters +1
    
  return inters, num_inters
  
def compute_inside_fractures_in_circle(fractures_lines, fractures_polylines, circle):
  #check if lines are inside the circle
  inside_lines = []
  num_additional_fractures = 0  #used to avoid to count polylines more than once
  
  for line in fractures_lines:
    start_inside = is_inside_circle([line[0],line[1]], circle)
    end_inside   = is_inside_circle([line[2],line[3]], circle)
    
    if(start_inside and end_inside):  #the whole line is contained
      inside_lines.append(line)
    elif(not start_inside and not end_inside):  #check if fractures traverses the whole scanarea
      inters, num_inters = circle_segment_intersection(circle, line)
      if num_inters == 2:
        inside_lines.append([inters[0][0], inters[0][1], inters[1][0], inters[1][1]])
    else:
      new_start = []
      if(start_inside):
        new_start = [line[0], line[1]]
      else:
        new_start = [line[2], line[3]]
      
      inters, _ = circle_segment_intersection(circle, line)
      inside_lines.append([new_start[0], new_start[1], inters[0][0], inters[0][1]])

  #check if polylines are inside the circle
  inside_polylines = []
  for poly in fractures_polylines:
    shrinked_poly = []
    started = False
    num_sub_polylines = 0
  
    #check if starts from inside the circle
    start_inside = is_inside_circle([poly[0][0],poly[0][1]], circle)
    if start_inside:
      shrinked_poly.append(poly[0])
      started = True
    
    for polypt_ind in range(1, len(poly)):
      poly_seg = poly[polypt_ind-1][0], poly[polypt_ind-1][1], poly[polypt_ind][0], poly[polypt_ind][1]
      poly_seg_intersect = False
      
      inters, num_inters = circle_segment_intersection(circle, poly_seg)
      for i in range(0, num_inters):
        shrinked_poly.append([inters[i][0], inters[i][1]])
        poly_seg_intersect = True
        if started:
          inside_polylines.append(shrinked_poly)
          num_sub_polylines = num_sub_polylines + 1
          shrinked_poly = []
          started = False
        else:
          started = True
      
      if poly_seg_intersect == True and started == True:
        shrinked_poly.append(poly[polypt_ind])
       
      if poly_seg_intersect == False and started == True:
        shrinked_poly.append(poly[polypt_ind])     
    
    if started == True:   #we are ending inside polygon
      inside_polylines.append(shrinked_poly)
      num_sub_polylines = num_sub_polylines + 1
    
    if num_sub_polylines > 1:
        num_additional_fractures = num_additional_fractures + num_sub_polylines - 1    
  
  print('\nNumber of internal fractures found: ',  len(inside_lines)+len(inside_polylines))
  text_box.insert("end", "\n\nNumber of internal fractures found: " + str(len(inside_lines)+len(inside_polylines)))
  return inside_lines, inside_polylines, num_additional_fractures

# extracts lengths and angles of fractures
def lengths_and_angles_extraction(fractures_lines, fractures_polylines, scale_factor):
  
  #lines analysis
  lines_vertical_angles = []
  lines_length          = []

  for line in fractures_lines:
    line_dir = line_direction(line)
    vertical_angle_rad = angle_wrapping(math.pi/2.0 + line_dir)
    lines_vertical_angles.append(rad_to_deg(vertical_angle_rad))
    lines_length.append(math.sqrt((line[2]-line[0])*(line[2]-line[0]) + (line[3]-line[1])*(line[3]-line[1])) * scale_factor)


  #polylines analysis
  polys_vertical_angles = []
  polys_length          = []

  for polyline in fractures_polylines:
    length = 0
    for pt_ind in range(len(polyline)-1):
      length += math.sqrt(pow(polyline[pt_ind+1][0]-polyline[pt_ind][0],2) + pow(polyline[pt_ind+1][1]-polyline[pt_ind][1],2))
    polys_length.append(length * scale_factor)
    equivalent_line = (polyline[0][0], polyline[0][1], polyline[len(polyline)-1][0], polyline[len(polyline)-1][1])
    eq_line_dir = line_direction(equivalent_line)
    vertical_angle_rad = angle_wrapping(math.pi/2.0 + eq_line_dir)
    polys_vertical_angles.append(rad_to_deg(vertical_angle_rad))

  #grouping the lines and polylines -> now lines will include also polylines
  lines_vertical_angles.extend(polys_vertical_angles)
  lines_length.extend(polys_length)

  #sorting
  lines_length, lines_vertical_angles  = (list(t) for t in zip(*sorted(zip(lines_length, lines_vertical_angles))))
  
  return lines_length, lines_vertical_angles
  
def intersection_analyzer():
  text_box.config(state="normal")
  text_box.delete(1.0, 'end')
  print('\n\nIntersection analysis started!')
  text_box.insert("end", "Intersection analysis started!")
  
  input_path = askopenfilename(title='Select File') # shows dialog box and return the path
  print("\nChosen path: ", input_path) 
  text_box.insert("end", "\n\nChosen path: " + input_path)

  if not os.path.isfile(input_path):
    print('Path not valid! Please enter a valid path to the file, thanks!')
    text_box.insert("end", "\nPath not valid! Please enter a valid path to the file, thanks!")
    return

  name_layer_fractures = "fractures"
  name_layer_scanline  = "scanline"
  name_layer_scale     = "scale"
    
  #open input file
  svg_file = open(input_path, "r")  
    
  #stacking all the lines
  file_rows = extract_lines_from_file(svg_file)         

  #find limits of scanline level
  start_primary_rows, end_primary_rows, scanline_found = find_layer_limits(name_layer_scanline, file_rows)
  if not scanline_found:
    return

  #find limits of fractures level
  start_secondary_rows, end_secondary_rows, fractures_found = find_layer_limits(name_layer_fractures, file_rows)
  if not fractures_found:
    return
    
  #find limits of scale level
  start_scale_rows, end_scale_rows, scale_found = find_layer_limits(name_layer_scale, file_rows)
  if not scale_found:
    return

  primary_lines        = []
  primary_polylines    = []
  secondary_lines      = []
  secondary_polylines  = []

  #reading primary lines
  for r_idx in range(start_primary_rows, end_primary_rows):
    if file_rows[r_idx].find("<line") != -1:
      primary_lines.append(read_line(file_rows[r_idx]))
    elif file_rows[r_idx].find("<polyline") != -1:
      primary_polylines.append(read_polyline(file_rows[r_idx]))
      
  print("\nScanline found: ", len(primary_lines))
  text_box.insert("end", "\n\nScanline found: " + str(len(primary_lines)))

  #reading secondary lines
  for r_idx in range(start_secondary_rows, end_secondary_rows):
    if file_rows[r_idx].find("<line") != -1:
      secondary_lines.append(read_line(file_rows[r_idx]))
    elif file_rows[r_idx].find("<polyline") != -1:
      secondary_polylines.append(read_polyline(file_rows[r_idx]))

  #calculating scale factor
  scale_factor = calculate_scale_factor(file_rows, start_scale_rows, end_scale_rows)
   
  print('\nNumber of fractures found: ',  len(secondary_lines)+len(secondary_polylines))
  text_box.insert("end", "\n\nNumber of fractures found: " + str(len(secondary_lines)+len(secondary_polylines)))
      
  #Analysis of intersection between lines and primary line
  primary_line = primary_lines[0]
  primary_dir  = line_direction(primary_line)

  lines_intersection_points = []
  proj_pint_scanlines_lines = []  
  lines_vertical_angles     = []
  lines_fractures_angles    = []
  lines_length              = []

  for line in secondary_lines:
    int_x, int_y = find_intersection_point(primary_line, line)
    if intersection_is_valid(int_x, int_y, primary_line, line):
      lines_intersection_points.append([int_x, int_y])
      proj_pint_scanlines_lines.append(line_projection(int_x, int_y, primary_line) * scale_factor)
      lines_length.append(math.sqrt((line[2]-line[0])*(line[2]-line[0]) + (line[3]-line[1])*(line[3]-line[1])) * scale_factor)
      line_dir = line_direction(line)
      vertical_angle_rad = angle_wrapping(math.pi/2.0 + line_dir)
      lines_vertical_angles.append(rad_to_deg(vertical_angle_rad))
      angolo_frattura_rad = angle_wrapping(primary_dir + line_dir)
      lines_fractures_angles.append(rad_to_deg(angolo_frattura_rad))

  #Analysis of intersection between polylines and primary line
  polys_intersection_points = []
  proj_pint_scanline_polys  = []
  polys_vertical_angles     = []
  polys_fractures_angles    = []
  polys_length              = []

  for polyline in secondary_polylines:
    int_found = False
    for pt_ind in range(len(polyline)-1):
      subline = [polyline[pt_ind][0], polyline[pt_ind][1], polyline[pt_ind+1][0], polyline[pt_ind+1][1]]
      int_x, int_y = find_intersection_point(primary_line, subline)
      if intersection_is_valid(int_x, int_y, primary_line, subline):
        int_found = True
        break
    
    if int_found == True:
      polys_intersection_points.append([int_x, int_y])
      proj_pint_scanline_polys.append(line_projection(int_x, int_y, primary_line) * scale_factor)
      length = 0
      for pt_ind in range(len(polyline)-1):
        length += math.sqrt(pow(polyline[pt_ind+1][0]-polyline[pt_ind][0],2) + pow(polyline[pt_ind+1][1]-polyline[pt_ind][1],2))
      polys_length.append(length * scale_factor)
      
      equivalent_line = (polyline[0][0], polyline[0][1], polyline[len(polyline)-1][0], polyline[len(polyline)-1][1])
      eq_line_dir = line_direction(equivalent_line)
      vertical_angle_rad = angle_wrapping(math.pi/2.0 + eq_line_dir)
      polys_vertical_angles.append(rad_to_deg(vertical_angle_rad))
      angolo_frattura_rad = angle_wrapping(primary_dir + eq_line_dir)
      polys_fractures_angles.append(rad_to_deg(angolo_frattura_rad))
   
  #grouping the lines and polylines -> now lines will include also polylines
  lines_intersection_points.extend(polys_intersection_points)
  proj_pint_scanlines_lines.extend(proj_pint_scanline_polys)
  lines_vertical_angles.extend(polys_vertical_angles)
  lines_fractures_angles.extend(polys_fractures_angles)
  lines_length.extend(polys_length)

  print("\nNumber of intersections found:  ", len(lines_intersection_points))
  text_box.insert("end", "\n\nNumber of intersections found:  " + str(len(lines_intersection_points)))

  #sorting
  proj_pint_scanlines_lines, lines_intersection_points, lines_vertical_angles, lines_fractures_angles, lines_length = (list(t) for t in zip(*sorted(zip(proj_pint_scanlines_lines, lines_intersection_points, lines_vertical_angles, lines_fractures_angles, lines_length))))
  
  #computing apparent spacing
  apparent_spacings = []
  if(len(proj_pint_scanlines_lines) > 0):
    apparent_spacings.append(proj_pint_scanlines_lines[0])
    apparent_spacings.extend([proj_pint_scanlines_lines[pp_ind]-proj_pint_scanlines_lines[pp_ind-1] for pp_ind in range(1, len(proj_pint_scanlines_lines))])
   
  #saving output
  out_file = open(os.path.splitext(input_path)[0]+"_intersections.txt", "w")

  scanline_angle_rad  = angle_wrapping(math.pi/2.0 + primary_dir)
  scanline_angle_grad = rad_to_deg(scanline_angle_rad)
  scanline_length     = math.sqrt(pow(primary_line[2]-primary_line[0],2)+pow(primary_line[3]-primary_line[1],2)) * scale_factor
  out_file.write("SCANLINE LENGTH: " + "{:.3f}".format(scanline_length) + "   ORIENTATION: " + "{:.3f}".format(scanline_angle_grad) + "\n" + "\n")

  out_file.write("{: <10} {: <30} {: <30} {: <30} {: <30} {: <30}".format("NUM", "DISTANCE FROM ORIGIN", "APPARENT SPACING", "LENGTH", "STRIKE ANGLE", "SCANLINE to FRACTURE ANGLE"))
  out_file.write('\n')

  #saving lines+polylines
  for l in range(0, len(lines_intersection_points)):
    out_file.write("{: <10} {: <30} {: <30} {: <30} {: <30} {: <30}".format(l+1, "{:.3f}".format(proj_pint_scanlines_lines[l]), "{:.3f}".format(apparent_spacings[l]), "{:.3f}".format(lines_length[l]), "{:.3f}".format(lines_vertical_angles[l]), "{:.3f}".format(lines_fractures_angles[l])))
    out_file.write('\n')

  out_file.close()

  #DEBUG DRAW

  #find max values
  x_max = 0
  y_max = 0
  for line in secondary_lines:
    if line[0] > x_max:
      x_max = line[0]
    if line[2] > x_max:
      x_max = line[2]
    if line[1] > y_max:
      y_max = line[1]
    if line[3] > y_max:
      y_max = line[3]
      
  for polyline in secondary_polylines:
    for pt in polyline:
      if pt[0] > x_max:
        x_max = pt[0]
      if pt[1] > y_max:
        y_max = pt[1]

  im = Image.new('RGBA', (int(x_max)+5, int(y_max)+5), (255, 255, 255, 255)) 
  draw = ImageDraw.Draw(im) 

  #primary lines
  for line_pts in primary_lines:
    draw.line(line_pts, fill ="red", width=1)

  #secondary lines
  for line_pts in secondary_lines:
    draw.line(line_pts, fill ="blue", width=1)

  #lines intersections
  for intersection in lines_intersection_points:
    draw.ellipse([intersection[0]-1, intersection[1]-1, intersection[0]+1, intersection[1]+1], fill = 'yellow', outline ='yellow', width=1)
    
  #secondary polylines
  for polyline in secondary_polylines:
    for pt_ind in range(len(polyline)-1):
      subline = [polyline[pt_ind][0], polyline[pt_ind][1], polyline[pt_ind+1][0], polyline[pt_ind+1][1]]
      draw.line(subline, fill ="green", width=1)
    
  #polylines intersections
  for intersection in polys_intersection_points:
    draw.ellipse([intersection[0]-1, intersection[1]-1, intersection[0]+1, intersection[1]+1], fill = 'yellow', outline ='yellow', width=1)

  im.show()

  svg_file.close()


def fracture_list_generator():
  text_box.config(state="normal")
  text_box.delete(1.0, 'end')
  print('\n\nFractures list generation started!')
  text_box.insert("end", "Fractures list generation started!")
      
  input_path = askopenfilename(title='Select File') # shows dialog box and return the path
  print("\nChosen path: ", input_path) 
  text_box.insert("end", "\n\nChosen path: " + input_path)

  if not os.path.isfile(input_path):
    print('Path not valid! Please enter a valid path to the file, thanks!')
    text_box.insert("end", "\nPath not valid! Please enter a valid path to the file, thanks!")
    return

  name_layer_fractures = "fractures"
  name_layer_scale     = "scale"
    
  #open input file
  svg_file = open(input_path, "r")  
  
  #stacking all the lines
  file_rows = extract_lines_from_file(svg_file) 

  #find limits fractures level
  start_fractures_rows, end_fractures_rows, fractures_found = find_layer_limits(name_layer_fractures, file_rows)
  if not fractures_found:
    return

  #find limits scale level
  start_scale_rows, end_scale_rows, scale_found = find_layer_limits(name_layer_scale, file_rows)
  if not scale_found:
    return
    
  fractures_lines     = []
  fractures_polylines = []

  #reading fractures
  for r_idx in range(start_fractures_rows, end_fractures_rows):
    if file_rows[r_idx].find("<line") != -1:
      fractures_lines.append(read_line(file_rows[r_idx]))
    elif file_rows[r_idx].find("<polyline") != -1:
      fractures_polylines.append(read_polyline(file_rows[r_idx]))

  #scale factor computation
  scale_factor = calculate_scale_factor(file_rows, start_scale_rows, end_scale_rows)
   
  print('\nNumber of fractures found: ',  len(fractures_lines)+len(fractures_polylines))
  text_box.insert("end", "\n\nNumber of fractures found: " + str(len(fractures_lines)+len(fractures_polylines)))
   
  fractures_lengths, fractures_vertical_angles = lengths_and_angles_extraction(fractures_lines, fractures_polylines, scale_factor)
   
  #saving output
  out_file = open(os.path.splitext(input_path)[0]+"_fractures_list.txt", "w")

  out_file.write("{: <10} {: <30} {: <30}".format("NUM", "LENGTH", "STRIKE ANGLE"))
  out_file.write('\n')

  #salvataggio lines+polylines
  for l in range(0, len(fractures_lengths)):
    out_file.write("{: <10} {: <30} {: <30}".format(l+1, "{:.3f}".format(fractures_lengths[l]), "{:.3f}".format(fractures_vertical_angles[l])))
    out_file.write('\n')

  out_file.close()

  #DEBUG DRAW

  #find max values
  x_max = 0
  y_max = 0
  for line in fractures_lines:
    if line[0] > x_max:
      x_max = line[0]
    if line[2] > x_max:
      x_max = line[2]
    if line[1] > y_max:
      y_max = line[1]
    if line[3] > y_max:
      y_max = line[3]
      
  for polyline in fractures_polylines:
    for pt in polyline:
      if pt[0] > x_max:
        x_max = pt[0]
      if pt[1] > y_max:
        y_max = pt[1]

  im = Image.new('RGBA', (int(x_max)+5, int(y_max)+5), (255, 255, 255, 255)) 
  draw = ImageDraw.Draw(im) 

  #secondary lines
  for line_pts in fractures_lines:
    draw.line(line_pts, fill ="blue", width=1)
    
  #secondary polylines
  for polyline in fractures_polylines:
    for pt_ind in range(len(polyline)-1):
      subline = [polyline[pt_ind][0], polyline[pt_ind][1], polyline[pt_ind+1][0], polyline[pt_ind+1][1]]
      draw.line(subline, fill ="green", width=1)

  im.show()
  svg_file.close()
  
def fracture_density_computation():
  text_box.config(state="normal")
  text_box.delete(1.0, 'end')
  print('\n\nFractures density computation started!')
  text_box.insert("end", "Fractures density computation started!")
  
  input_path = askopenfilename(title='Select File') # shows dialog box and return the path
  print("\nChosen path: ", input_path)
  text_box.insert("end", "\n\nChosen path: " + input_path)

  if not os.path.isfile(input_path):
    print('Path not valid! Please enter a valid path to the file, thanks!')
    text_box.insert("end", "\nPath not valid! Please enter a valid path to the file, thanks!")
    return

  name_layer_fractures = "fractures"
  name_layer_scanarea    = "scanarea"
  name_layer_scale     = "scale"
    
  #open input file
  svg_file = open(input_path, "r")  
    
  #stacking all the lines
  file_rows = extract_lines_from_file(svg_file) 

  #find limits scanlines level
  start_fractures_rows, end_fractures_rows, fractures_found = find_layer_limits(name_layer_fractures, file_rows)
  if not fractures_found:
    return

  #find limits scanarea level
  start_scanarea_rows, end_scanarea_rows, scanarea_found = find_layer_limits(name_layer_scanarea, file_rows)
  if not scanarea_found:
    return

  #find limits scale level
  start_scale_rows, end_scale_rows, scale_found = find_layer_limits(name_layer_scale, file_rows)
  if not scale_found:
    return

  #scale factor calculation
  scale_factor = calculate_scale_factor(file_rows, start_scale_rows, end_scale_rows)

  fractures_lines       = []
  fractures_polylines   = []
  lines_scanarea       = []
  polylines_scanarea   = []

  #reading primary lines-polylines
  for r_idx in range(start_fractures_rows, end_fractures_rows):
    if file_rows[r_idx].find("<line") != -1:
      fractures_lines.append(read_line(file_rows[r_idx]))
    elif file_rows[r_idx].find("<polyline") != -1:
      fractures_polylines.append(read_polyline(file_rows[r_idx]))    
      
  print('\nNumber of total fractures found: ',  len(fractures_lines)+len(fractures_polylines))
  text_box.insert("end", "\n\nNumber of total fractures found: " + str(len(fractures_lines)+len(fractures_polylines)))

  #reading lines-polylines-circle scanarea
  scanarea_is_circular = False
  for r_idx in range(start_scanarea_rows, end_scanarea_rows):
    if file_rows[r_idx].find("<line") != -1:
      lines_scanarea.append(read_line(file_rows[r_idx]))
    elif file_rows[r_idx].find("<polyline") != -1:
      polylines_scanarea.append(read_polyline(file_rows[r_idx]))
    elif file_rows[r_idx].find("<polygon") != -1:
      polylines_scanarea.append(read_polygon(file_rows[r_idx]))
    elif file_rows[r_idx].find("<rect") != -1:
      lines_scanarea.extend(read_rect(file_rows[r_idx]))
      break
    elif file_rows[r_idx].find("<circle") != -1:
      scanarea_circle = read_circle(file_rows[r_idx])
      scanarea_is_circular = True
      break
      
  if not scanarea_is_circular:
    #creating single list of lines for the scanarea
    scanarea_polygon = lines_scanarea.copy()
    
    for poly in polylines_scanarea:
      for pt_ind in range(0, len(poly)-1):
        scanarea_polygon.append([poly[pt_ind][0], poly[pt_ind][1], poly[pt_ind+1][0], poly[pt_ind+1][1]])
    
    if(scanarea_polygon[0][0] != scanarea_polygon[len(scanarea_polygon)-1][2] or scanarea_polygon[0][1] != scanarea_polygon[len(scanarea_polygon)-1][3]):
      print('\nScanarea segments are not closed, please correct the scanarea layer')
      text_box.insert("end", "\nScanarea segments are not closed, please correct the scanarea layer")
      return
      
    print('\nNumber of sides of the scanarea: ',  len(scanarea_polygon))
    text_box.insert("end", "\n\nNumber of sides of the scanarea: " + str(len(scanarea_polygon)))
    
    inside_lines, inside_polylines, num_additional_fractures = compute_inside_fractures_in_polygon(fractures_lines, fractures_polylines, scanarea_polygon)  
    
    #computing area for polygon
    area_scanarea = 0.5 * abs(sum(line[0]*line[3] - line[2]*line[1] for line in scanarea_polygon)) * scale_factor * scale_factor
    
  else:  #scanarea is circular
    inside_lines, inside_polylines, num_additional_fractures = compute_inside_fractures_in_circle(fractures_lines, fractures_polylines, scanarea_circle)   
    
    #computing area for circle
    area_scanarea = scanarea_circle[2]*scanarea_circle[2]*math.pi*scale_factor*scale_factor
    
  if(len(inside_lines) == 0 and len(inside_polylines) == 0):
    print("\nI can't proceed without internal fractures, sorry!")
    text_box.insert("end", "\n\nI can't proceed without internal fractures, sorry!")
    svg_file.close()
    return

  
  #extracting fractures info
  fractures_lengths, fractures_vertical_angles = lengths_and_angles_extraction(inside_lines, inside_polylines, scale_factor)
  
  #computing P20 and P21 parameters
  num_fractures = len(fractures_lengths)
  cumulative_length_fratture = sum(fractures_lengths)
  
  P20 = num_fractures/area_scanarea
  P21 = cumulative_length_fratture/area_scanarea
  
  p20_p21_string = "P20: " + "{:.3f}".format(P20) + "  P21: " + "{:.3f}".format(P21) + "  Area of scanarea: " + "{:.3f}".format(area_scanarea)
  print('\nP20: ', "{:.3f}".format(P20), '  P21: ', "{:.3f}".format(P21), '  Area of scanarea: ', "{:.3f}".format(area_scanarea))
  text_box.insert("end", "\n\n" + p20_p21_string)
  
  #saving output
  out_file = open(os.path.splitext(input_path)[0]+"_scanarea_analysis.txt", "w")

  out_file.write("P20: " + "{:.3f}".format(P20) + "  P21: " + "{:.3f}".format(P21) + "\n" + "Area of scanarea: " + "{:.3f}".format(area_scanarea) + "  Num internal fractures: " + str(num_fractures) + "  Cumulative fractures length: " + "{:.3f}".format(cumulative_length_fratture) + "\n" + "\n")

  out_file.write("{: <10} {: <30} {: <30}".format("NUM", "LENGTH", "STRIKE ANGLE"))
  out_file.write('\n')

  #saving lines+polylines
  for l in range(0, len(fractures_lengths)):
    out_file.write("{: <10} {: <30} {: <30}".format(l+1, "{:.3f}".format(fractures_lengths[l]), "{:.3f}".format(fractures_vertical_angles[l])))
    out_file.write('\n')

  out_file.close()
  
  #DEBUG DRAW

  #find max values
  x_max = 0
  y_max = 0
  for line in fractures_lines:
    if line[0] > x_max:
      x_max = line[0]
    if line[2] > x_max:
      x_max = line[2]
    if line[1] > y_max:
      y_max = line[1]
    if line[3] > y_max:
      y_max = line[3]
      
  for polyline in fractures_polylines:
    for pt in polyline:
      if pt[0] > x_max:
        x_max = pt[0]
      if pt[1] > y_max:
        y_max = pt[1]

  im = Image.new('RGBA', (int(x_max)+5, int(y_max)+5), (255, 255, 255, 255)) 
  draw = ImageDraw.Draw(im) 

  #secondary lines
  for line_pts in fractures_lines:
    draw.line(line_pts, fill ="blue", width=1)
    
  #secondary polylines
  for polyline in fractures_polylines:
    for pt_ind in range(len(polyline)-1):
      subline = [polyline[pt_ind][0], polyline[pt_ind][1], polyline[pt_ind+1][0], polyline[pt_ind+1][1]]
      draw.line(subline, fill ="blue", width=1)
      
  #scanarea    
  if not scanarea_is_circular:
    for lato_pts in scanarea_polygon:
      draw.line(lato_pts, fill=(0,255,0), width=3)
  else:
    leftUpPoint = (scanarea_circle[0]-scanarea_circle[2], scanarea_circle[1]-scanarea_circle[2])
    rightDownPoint = (scanarea_circle[0]+scanarea_circle[2], scanarea_circle[1]+scanarea_circle[2])
    draw.arc([leftUpPoint, rightDownPoint], 0, 360, fill=(0,255,0), width=3)
      
  #secondary lines inside scanarea
  for line_pts in inside_lines:
    draw.line(line_pts, fill ="red", width=1)  
    
  #secondary polylines inside scanarea
  for polyline in inside_polylines:
    for pt_ind in range(len(polyline)-1):
      subline = [polyline[pt_ind][0], polyline[pt_ind][1], polyline[pt_ind+1][0], polyline[pt_ind+1][1]]
      draw.line(subline, fill ="red", width=1)

  im.show()
  svg_file.close()
          

#Start program
print("Welcome to the Fractures Analyzer " + version + "!")
print("\nSVG Layer names for the Find scanline intersections function: fractures, scale, scanline" + "\nSVG Layer names for the Compute scanarea density function: fractures, scale, scanarea" + "\nSVG Layer names for the Generate fracture list function: fractures, scale")
message = "Welcome to the Fractures Analyzer " + version + "!" + "\nSVG Layer names for the Find scanline intersections function: fractures, scale, scanline" + "\nSVG Layer names for the Compute scanarea density function: fractures, scale, scanarea" + "\nSVG Layer names for the Generate fracture list function: fractures, scale"

#Create tk context
parent = tk.Tk()
parent.title("FA " + version)
frame = tk.Frame(parent)
frame.pack()
button_font = Font(size=19)

#adding buttons 
row1_Frame = tk.Frame(frame)
row1_Frame.pack(side="top", fill="x")

intersection_button  = tk.Button(row1_Frame, text="Find scanline intersections", fg="green", command=intersection_analyzer)
intersection_button.pack(side=tk.LEFT)
intersection_button['font'] = button_font

fracture_list_button = tk.Button(row1_Frame, text="Generate fracture list", fg="blue", command=fracture_list_generator)
fracture_list_button.pack(side=tk.RIGHT)
fracture_list_button['font'] = button_font

row2_Frame = tk.Frame(frame)
row2_Frame.pack(side="top", fill="x")

scanarea_density_button = tk.Button(row2_Frame, text="Compute scanarea density", fg="purple", command=fracture_density_computation)
scanarea_density_button.pack(side=tk.LEFT)
scanarea_density_button['font'] = button_font

exit_button = tk.Button(row2_Frame, text="Exit", fg="red", command=quit)
exit_button.pack(side=tk.RIGHT)
exit_button['font'] = button_font

#text box
text_box = tk.Text(frame, height=25, width=80)
text_box.config(state="normal")
text_box.pack(expand=True)
text_box.insert('end', message)
text_box.config(state='disabled')

parent.mainloop()

