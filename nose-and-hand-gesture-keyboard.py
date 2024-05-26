import os
import cv2
import mediapipe as mp
import pyperclip
import time
import numpy as np

# Suppress TensorFlow Lite logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Initialize Mediapipe face mesh and hands, and drawing utilities
mp_face_mesh = mp.solutions.face_mesh
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

typed_word = ""
cooldown_time = 0.5  # Time in seconds to wait before allowing another letter to be added
last_key_press_time = 0

key_width, key_height = 60, 60  # Original smaller key size

def recognize_gesture(nose_tip_x, nose_tip_y, start_x, start_y):
    if start_x <= nose_tip_x < start_x + key_width * 10 and start_y <= nose_tip_y < start_y + key_height * 3:
        col = (nose_tip_x - start_x) // key_width
        row = (nose_tip_y - start_y) // key_height
        keys = "QWERTYUIOPASDFGHJKLZXCVBNM"
        index = row * 10 + col
        if index < len(keys):
            key = keys[index]
            return key
    # Check if the space or delete key is pressed
    if start_x + key_width * 4 <= nose_tip_x < start_x + key_width * 6 and start_y + key_height * 3 <= nose_tip_y < start_y + key_height * 4:
        return " "
    if start_x + key_width * 9 <= nose_tip_x < start_x + key_width * 10 and start_y + key_height * 3 <= nose_tip_y < start_y + key_height * 4:
        return "DELETE"
    return None

# Function to draw the virtual keyboard
def draw_virtual_keyboard(image, start_x, start_y, highlighted_key=None, typed_word=""):
    keys = "QWERTYUIOP\nASDFGHJKL\nZXCVBNM"
    for i, row in enumerate(keys.split('\n')):
        for j, key in enumerate(row):
            x = start_x + j * key_width
            y = start_y + i * key_height
            if key == highlighted_key:
                cv2.rectangle(image, (x, y), (x + key_width, y + key_height), (0, 255, 0), -1)
            else:
                cv2.rectangle(image, (x, y), (x + key_width, y + key_height), (255, 0, 0), 2)
            cv2.putText(image, key, (x + 10, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    # Draw the space key
    x = start_x + key_width * 4
    y = start_y + key_height * 3
    if highlighted_key == " ":
        cv2.rectangle(image, (x, y), (x + key_width * 2, y + key_height), (0, 255, 0), -1)
    else:
        cv2.rectangle(image, (x, y), (x + key_width * 2, y + key_height), (255, 0, 0), 2)
    cv2.putText(image, "SPACE", (x + 10, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    # Draw the delete key
    x = start_x + key_width * 9
    if highlighted_key == "DELETE":
        cv2.rectangle(image, (x, y), (x + key_width, y + key_height), (0, 255, 0), -1)
    else:
        cv2.rectangle(image, (x, y), (x + key_width, y + key_height), (255, 0, 0), 2)
    cv2.putText(image, "DEL", (x + 10, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    # Display the typed word
    cv2.putText(image, typed_word, (start_x, start_y + 4 * key_height + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.rectangle(image, (start_x, start_y + 4 * key_height + 60), (start_x + 150, start_y + 4 * key_height + 110), (0, 0, 255), 2)
    cv2.putText(image, "COPY", (start_x + 30, start_y + 4 * key_height + 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

# Function to check if the copy button is pressed
def is_copy_button_pressed(nose_tip_x, nose_tip_y, start_x, start_y):
    if start_x <= nose_tip_x <= start_x + 150 and start_y + 4 * key_height + 60 <= nose_tip_y <= start_y + 4 * key_height + 110:
        return True
    return False

# Capture video from webcam
cap = cv2.VideoCapture(0)

selected_key = None
with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5) as face_mesh, mp_hands.Hands(
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5) as hands:

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            break

        # Flip the image horizontally for a mirror effect
        image = cv2.flip(image, 1)

        # Convert the image color to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results_face = face_mesh.process(image_rgb)
        results_hands = hands.process(image_rgb)

        # Convert the image color back to BGR for OpenCV
        image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

        # Get image dimensions
        image_height, image_width, _ = image.shape

        # Calculate the starting position of the keyboard to center it
        start_x = (image_width - key_width * 10) // 2
        start_y = (image_height - key_height * 4) // 2

        # Create a copy of the image for displaying the virtual keyboard
        keyboard_image = image.copy()

        nose_tip = None
        right_hand_landmarks = None

        # Extract landmarks for nose tip
        if results_face.multi_face_landmarks:
            for face_landmarks in results_face.multi_face_landmarks:
                nose_tip = (int(face_landmarks.landmark[1].x * image_width),  # Nose tip index is 1
                            int(face_landmarks.landmark[1].y * image_height))
        
        # Extract right hand landmarks
        if results_hands.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results_hands.multi_hand_landmarks, results_hands.multi_handedness):
                if handedness.classification[0].label == "Right":
                    right_hand_landmarks = hand_landmarks

        # Recognize gesture from nose to select key
        if nose_tip:
            selected_key = recognize_gesture(nose_tip[0], nose_tip[1], start_x, start_y)

        # Recognize gesture from right hand to press key or copy button
        if right_hand_landmarks:
            landmarks = right_hand_landmarks.landmark
            index_finger_tip_y = int(landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y * image_height)
            index_finger_mcp_y = int(landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].y * image_height)

            if index_finger_tip_y < index_finger_mcp_y and time.time() - last_key_press_time > cooldown_time:
                if selected_key:
                    if selected_key == "DELETE":
                        typed_word = typed_word[:-1]
                    else:
                        typed_word += selected_key
                    selected_key = None
                    last_key_press_time = time.time()

        draw_virtual_keyboard(keyboard_image, start_x, start_y, selected_key, typed_word)

        # Display the resulting frames
        cv2.imshow('Face Gestures', image)
        cv2.imshow('Virtual Keyboard', keyboard_image)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()