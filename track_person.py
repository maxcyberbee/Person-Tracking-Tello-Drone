#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pygame.locals import *
import posenet
import argparse


from utils import CvFpsCalc

from gestures import *


import time
import sys
import cyberbee
import datetime
import os
import keyboard
import pygame
import cv2
import numpy
import av
import threading
import traceback
from simple_pid import PID
import tensorflow.compat.v1 as tf

from includes import get_args, getAviNameWithDate, CalculateControl
import pyvirtualcam
import json 

import socket
import pygame

from sys import stdout
# Initialize pygame for joystick support
pygame.display.init()
pygame.joystick.init()

controller = pygame.joystick.Joystick(0)
controller.init()

tf.disable_v2_behavior()


#


prev_flight_data = None
run_controller_thread = True
shutdown = False
# drone control inputs
drone_cc = 0  # rotation command
drone_ud = 0  # up/down command
drone_fb = 0  # forward/backward command

framerate = 30.0

filename = "temp"

start_hand_landing = False  # true when gesture recognized
ready_to_land = False  # true when size of body match the requested
# number of pixel for size of body in frame (distance control)
desiredHeight = 70
# number of pixel for size of body in frame for landing in hand  (distance control)
landing_height = 130
landing_timeout = 0
up_count = 0  # number of up gestures recognized
take_of_from_gesture_count = 5
last_up_time_mili = 0
gesture_take_off = False
last_locked_position = [0, 0]
last_body_height = 0
took_off = False
control_on = False
stop_gesture = False
new_image_ready = False
gesture_start_control = False
stopped_lr = False
current_height, speed, battery, wifi_quality = 0, 0, 0, 0
lr_timeout = 0
time_out_LR = 500
json_to_send = json.loads('{ "Height":-1, "Speed":-1, "Battery":-1, "Wifi_quality":-1}')
tracker_on = False
bbox = (0,0,0,0)
TCP_IP = '127.0.0.1'
TCP_PORT = 7000
BUFFER_SIZE = 1024
MESSAGE = "Hello, World!"

def controller_thread():
    global drone
    global drone_cc
    global drone_ud
    global drone_fb
    global shutdown
    global gesture_take_off
    global took_off
    global ready_to_land
    global start_hand_landing
    global control_on
    global stop_gesture
    global gesture_start_control
    global lr_timeout
    global stopped_lr
    # initialize previous drone control inputs
    control_on = True  # allows you to toggle control so that you can force landing
    pdrone_cc = -111
    pdrone_ud = -111
    pdrone_fb = -111

    global run_controller_thread
    print('start controller_thread()')
    try:
        while run_controller_thread:
            time.sleep(.03)
            # takeoff
            if keyboard.is_pressed('space'):
                drone.takeoff()
                control_on = True
                took_off = True
            # land
            elif keyboard.is_pressed('l'):
                drone.land()
                control_on = False  # disable control
                # shutdown = True
                took_off = False
                start_hand_landing = False
                ready_to_land = False

            elif keyboard.is_pressed('q'):
                drone.counter_clockwise(40)
            elif keyboard.is_pressed('e'):
                drone.clockwise(40)
            elif keyboard.is_pressed('d'):
                drone.right(40)
            elif keyboard.is_pressed('a'):
                drone.left(40)
            elif keyboard.is_pressed('w'):
                drone.forward(40)
            elif keyboard.is_pressed('s'):
                drone.backward(40)
            elif keyboard.is_pressed('r'):
                drone.clockwise(0)
                drone.forward(0)
                drone.left(0)
            elif keyboard.is_pressed('t'):  # toggle controls
                control_on = not control_on
            elif keyboard.is_pressed('esc'):
                drone.land()
                break

            # set commands based on PID output
            if control_on and (pdrone_cc != drone_cc):
                if drone_cc < 0:
                    drone.clockwise(min([40, (int(drone_cc)*-1)]))
                else:
                    drone.counter_clockwise(min([40, int(drone_cc)]))
                pdrone_cc = drone_cc
            if control_on and (pdrone_ud != drone_ud):
                if drone_ud < 0:
                    # easily moving downwards requires control output to be magnified
                    drone.down(min([100, (int(drone_ud)*-2)]))
                else:
                    drone.up(min([200, int(drone_ud)]))
                pdrone_ud = drone_ud
            if control_on and (pdrone_fb != drone_fb):
                if drone_fb < 0:
                    # easily moving backwards requires control output to be magnified
                    drone.backward(min([40, int(drone_fb)*-1]))
                else:
                    if(start_hand_landing):
                        drone.forward(min([20, int(drone_fb)]))
                    else:
                        drone.forward(min([30, int(drone_fb)]))
                pdrone_fb = drone_fb

            if(gesture_take_off):
                gesture_take_off = False
                time.sleep(0.2)
                drone.throw_and_go()
                took_off = True
                time.sleep(0.1)
                drone.up(20)
                time.sleep(0.1)
                drone.backward(20)
                time.sleep(0.1)
                drone.up(20)
                time.sleep(0.1)
                drone.backward(20)

            if(ready_to_land and 3500 < (round(time.time() * 1000) - landing_timeout)):
                print("-----------------landing-----------------------")
                drone.palm_land()
                control_on = False  # disable control
                start_hand_landing = False
                took_off = False
                ready_to_land = False

            # if(stop_gesture):
            #     stop_gesture = False
            #     control_on = False  # disable control
            #     drone.clockwise(0)
            #     drone.forward(0)
            #     drone.left(0)

            if(gesture_start_control):
                gesture_start_control = False
                control_on = True  # disable control

            # move right/left finished
            if(time_out_LR < round(time.time() * 1000) - lr_timeout and not time_out_LR < 2*round(time.time() * 1000) - lr_timeout):
                drone.left(0)
                
            pygame.event.pump()
            
            roll = 20* controller.get_axis(0)
            pitch = 20* controller.get_axis(1)
            yaw = 20* controller.get_axis(3)
            gaz = 20* controller.get_axis(2)
            
            if(1 == controller.get_axis(6)):
                control_on = False
                drone.clockwise(yaw)                
                drone.up(gaz)               
                drone.forward(pitch)
                drone.right(roll)
                
            else:
                control_on = True
                    
                
            
            

            # stdout.write('%s | Axes: ' % controller.get_name())

            # for k in range(controller.get_numaxes()):
            #     stdout.write('%d:%+2.2f ' % (k, controller.get_axis(k)))
            # stdout.write(' | Buttons: ')
            # for k in range(controller.get_numbuttons()):
            #     stdout.write('%d:%d ' % (k, controller.get_button(k)))
            # stdout.write('\n')
                

    except KeyboardInterrupt as e:
        print(e)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print(e)
    finally:
        run_controller_thread = False

def TCP_ResponceThread():
    global json_to_send
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(1)
    conn, addr = s.accept()
    print ('Connection address:', addr)
    while not shutdown:
        data = conn.recv(BUFFER_SIZE)
        if not data: break
        print ("received data:", data)
        conn.send(json_to_send)  # echo
    conn.close()

def handler(event, sender, data, **args):
    global prev_flight_data
    global current_height, speed, battery, wifi_quality
    global json_to_send

    drone = sender
    if event is drone.EVENT_FLIGHT_DATA:
        if prev_flight_data != str(data):
            mylist = str(data).split(" ")
            mylist = list(filter(None, mylist))            
            current_height = int(mylist[1])
            speed = int(mylist[4])
            battery = int(mylist[7])
            wifi_quality = int(mylist[10])
            json_string =  {
                "Height": current_height,
                "Speed": speed,
                "Battery": battery,
                "Wifi_quality": wifi_quality
            }
            
            
            json_to_send = json.dumps(json_string)
            print(json_to_send)
            prev_flight_data = str(data)
    else:
        print('event="%s" data=%s' % (event.getname(), str(data)))


def ShowVideos( overlay_image, debug_image, video):

    # im = numpy.array(frame.to_image())
    # im = cv2.resize(im, (960, 720))  # resize frame
    # image = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)    
    #show tracking + body recognition
    p1 = (int(bbox[0]), int(bbox[1]))
    p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
    cv2.rectangle(overlay_image, p1, p2, (255,0,0), 2, 1)
    overlay_image = cv2.resize(overlay_image, (960, 720))
    cv2.imshow('posenet', overlay_image)

    debug_image = cv2.resize(debug_image, (960, 720))
    cv2.imshow('Tello Gesture Recognition', debug_image)

    video.write(overlay_image)

    cv2.waitKey(1)


def gesture_control(gesture_buffer):
    global drone_cc, drone_ud, drone_fb, control_on, shutdown, run_controller_thread
    global desiredHeight, landing_timeout, start_hand_landing
    global up_count  # safe from false gesture
    global last_up_time_mili
    global gesture_take_off
    global stop_gesture
    global gesture_start_control
    global lr_timeout
    global stopped_lr
    
    gesture_id = gesture_buffer.get_gesture()

    print("GESTURE", gesture_id)

    if (gesture_id == 2 or gesture_id == 0):  # UP / Forward - Take off
        if(1000 < round(time.time() * 1000)-last_up_time_mili):
            up_count = 0
        last_up_time_mili = round(time.time() * 1000)
        up_count += 1
        if(take_of_from_gesture_count < up_count):
            if(not start_hand_landing or not took_off):
                gesture_take_off = True
            elif(took_off):
                control_on = True
                gesture_start_control = True

    if gesture_id == 3:  # LAND
        if(not start_hand_landing):
            desiredHeight = landing_height
            start_hand_landing = True
            landing_timeout = round(time.time() * 1000)

    elif gesture_id == 7:  # LEFT
        if(time_out_LR < round(time.time() * 1000) - lr_timeout):
            lr_timeout = round(time.time() * 1000)
            drone.left(20)
            stopped_lr = False

    elif gesture_id == 6:  # RIGHT
        if(time_out_LR < round(time.time() * 1000) - lr_timeout):
            lr_timeout = round(time.time() * 1000)
            drone.right(20)
            stopped_lr = False



def Stream_Video():
    global new_image_ready
    global new_frame
    with pyvirtualcam.Camera(width=960, height=720, fps=30) as cam: 
        if(new_image_ready):
            #print("write frame ----------------------")
            new_image_ready = False
            im_save = numpy.array(new_frame.to_image())
            im_save = cv2.resize(im_save, (960, 720))
            im_save = cv2.cvtColor(im_save, cv2.COLOR_RGB2BGR)
            out_video_save.write(im_save)
            cam.send(im_save)
            
            #out_stream.write(im_save)
        time.sleep(0.01)

def ObjectTracker():
    global tracking_ok, bbox,tracker_initilaized
    tracker = cv2.TrackerMedianFlow_create()
    fail_count = 0
    while not shutdown and tracker_on:
        if(new_image_ready):              
            frame = numpy.array(new_frame.to_image())
            # Start timer
            if(not (0,0,0,0) == bbox and not tracker_initilaized):  
                tracker_initilaized = True   
                ok = tracker.init(frame, bbox)

            # Update tracker
            elif(tracker_initilaized and tracking_ok):
                ok, bbox = tracker.update(frame)         

                
                if ok:
                   fail_count = 0
                    
                else :
                    fail_count +=1
                    if(30 < fail_count):
                        tracking_ok = False
                    # Tracking failure
                
    
       

def main():
    global drone

    global shutdown
    global gesture_buffer
    global gesture_id
    global battery_status
    global new_frame
    global new_image_ready
    global drone_cc
    global drone_ud
    global drone_fb
    global control_on
    global last_locked_position
    global ready_to_land
    global bbox
   
    args_gest = get_args()
    gesture_detector = GestureRecognition(args_gest.use_static_image_mode, args_gest.min_detection_confidence,
                                          args_gest.min_tracking_confidence)
    gesture_buffer = GestureBuffer(buffer_len=args_gest.buffer_len)

    mode = 0
    number = -1
    battery_status = -1
    drone_class = cyberbee.CyberBee()
    drone = drone_class.GetDrone()

    drone.connect()
    drone.wait_for_connection(2.0)
    drone.start_video()

    drone.subscribe(drone.EVENT_FLIGHT_DATA, handler)
    pid_cc = PID(0.40, 0.10, 0.17, setpoint=0, output_limits=(-100, 100))
    pid_ud = PID(0.3, 0.05, 0.15, setpoint=0, output_limits=(-80, 80))
    pid_fb = PID(0.4, 0.10, 0.25, setpoint=0, output_limits=(-50, 50))

    # video = cv2.VideoWriter('test_out.avi', -1, 1, (320, 240))
    # drone.subscribe(drone.EVENT_VIDEO_FRAME,handler)
    print("Start Running")
    with tf.Session() as sess:
        model_cfg, model_outputs = posenet.load_model(args_gest.model, sess)
        output_stride = model_cfg['output_stride']

        try:
            # threading.Thread(target=recv_thread).start()
            threading.Thread(target=controller_thread).start()
            threading.Thread(target=Stream_Video).start()
            threading.Thread(target=ObjectTracker).start()
            
            container = av.open(drone.get_video_stream())
            frame_count = 0
            while not shutdown:
                for frame in container.decode(video=0):
                    frame_count = frame_count + 1
                    new_frame = frame
                    new_image_ready = True

                    # skip first 100 frames
                    if frame_count < 200:
                        continue
                    if frame_count % 4 == 0:
                        im = numpy.array(frame.to_image())
                        im = cv2.resize(im, (320, 240))  # resize frame
                        image = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)
                        input_image, display_image, output_scale = posenet.process_input(
                            image, scale_factor=args_gest.scale_factor, output_stride=output_stride)

                        heatmaps_result, offsets_result, displacement_fwd_result, displacement_bwd_result = sess.run(
                            model_outputs,
                            feed_dict={'image:0': input_image}
                        )

                        pose_scores, keypoint_scores, keypoint_coords = posenet.decode_multi.decode_multiple_poses(
                            heatmaps_result.squeeze(axis=0),
                            offsets_result.squeeze(axis=0),
                            displacement_fwd_result.squeeze(axis=0),
                            displacement_bwd_result.squeeze(axis=0),
                            output_stride=output_stride,
                            max_pose_detections=10,
                            min_pose_score=0.5)

                        keypoint_coords *= output_scale

                        # TODO this isn't particularly fast, use GL for drawing and display someday...
                        overlay_image = posenet.draw_skel_and_kp(
                            display_image, pose_scores, keypoint_scores, keypoint_coords,
                            min_pose_score=0.15, min_part_score=0.1)

                        drone_cc, drone_ud, drone_fb, control_on, last_locked_position, ready_to_land,bbox = CalculateControl(
                            control_on, keypoint_scores, keypoint_coords, pid_cc, pid_ud, pid_fb, overlay_image, start_hand_landing, desiredHeight)
                        debug_image, gesture_id = gesture_detector.recognize( image, number, mode)
                        gesture_buffer.add_gesture(gesture_id)
                        gesture_control(gesture_buffer)
                        ShowVideos(overlay_image,debug_image, out_video_save)

        except KeyboardInterrupt as e:
            print(e)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            print(e)

    cv2.destroyAllWindows()
    out_video_save.release()
    drone.quit()
    exit(1)


if __name__ == '__main__':
    global out_video_save
    filename = getAviNameWithDate("output_videos/output.avi")
    fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
    out_video_save = cv2.VideoWriter(filename, fourcc, 30, (960, 720))
    main()
