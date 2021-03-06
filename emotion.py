from statistics import mode
from keras.models import load_model
from utils.datasets import get_labels
from utils.inference import detect_faces
from utils.inference import draw_text
from utils.inference import draw_bounding_box
from utils.inference import apply_offsets
from utils.inference import load_detection_model
from utils.preprocessor import preprocess_input
import paho.mqtt.client as mqtt
import numpy as np
import json
import cv2
import time
import threading

def thread_mqtt():
    global mqtt_msg
    global stop_threads
    global state_thread_mqtt
    while True :
        if state_thread_mqtt :
            client.publish("python/mqtt", mqtt_msg, qos=0)
            print(mqtt_msg)
            time.sleep(2)
        if stop_threads :
            break

detection_model_path = 'trained_models/detection_models/haarcascade_frontalface_default.xml'
emotion_model_path = 'trained_models/emotion_models/fer2013_mini_XCEPTION.102-0.66.hdf5'
emotion_labels = get_labels('fer2013')

# hyper-parameters for bounding boxes shape
frame_window = 5
emotion_offsets = (10, 10)

# loading models
face_detection = load_detection_model(detection_model_path)
emotion_classifier = load_model(emotion_model_path)
emotion_text = ''
# getting input model shapes for inference
emotion_target_size = emotion_classifier.input_shape[1:3]

# starting lists for calculating modes
emotion_window = []

#mqtt 
mqtt_msg = ''
client = mqtt.Client("P1")
client.connect("touch-mqtt.touch-ics.com",1883)

# threading
state_thread_mqtt = False
stop_threads = False
thr = threading.Thread(target=thread_mqtt)
thr.start()

#starting video streaming
cv2.namedWindow('window_frame')
video_capture = cv2.VideoCapture(0)
while True:
    state_thread_mqtt = True
    emotion_text = ''
    faces=[]
    bgr_image = video_capture.read()[1]
    gray_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    faces = detect_faces(face_detection, gray_image)
    for face_coordinates in faces: 
        x1, x2, y1, y2 = apply_offsets(face_coordinates, emotion_offsets)
        gray_face = gray_image[y1:y2, x1:x2]
        try:
            gray_face = cv2.resize(gray_face, (emotion_target_size))
        except:
            continue
        gray_face = preprocess_input(gray_face, True)
        gray_face = np.expand_dims(gray_face, 0)
        gray_face = np.expand_dims(gray_face, -1)
        emotion_prediction = emotion_classifier.predict(gray_face)
        emotion_probability = np.max(emotion_prediction)
        emotion_label_arg = np.argmax(emotion_prediction)
        emotion_text = emotion_labels[emotion_label_arg]
        emotion_window.append(emotion_text)
        if len(emotion_window) > frame_window:
            emotion_window.pop(0)
        try:
            emotion_mode = mode(emotion_window)
        except:
            continue
        if emotion_text == 'angry':
            color = emotion_probability * np.asarray((255, 0, 0))
        elif emotion_text == 'happy':
            color = emotion_probability * np.asarray((255, 255, 0))
        else:
            color = emotion_probability * np.asarray((0, 255, 0))
        color = color.astype(int)
        color = color.tolist()
        draw_bounding_box(face_coordinates, rgb_image, color)
        draw_text(face_coordinates, rgb_image, emotion_mode,color, 0, -20, 1, 1)
    
    if len(faces)>0: 
        state_face_detect = True
    else :
        state_face_detect = False
    mqtt_msg = json.dumps({"face":state_face_detect, "emotion": emotion_text})
    # print(mqtt_msg)

    bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    cv2.imshow('window_frame', bgr_image)
  
    if cv2.waitKey(1) & 0xFF == ord('q'):
        stop_threads = True
        thr.join()
        break

video_capture.release()
cv2.destroyAllWindows()

