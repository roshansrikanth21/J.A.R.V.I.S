import cv2
import os

class FaceRecognitionTool:
    def __init__(self, model_path="k:/E.D.I.T.H/extracted_jarvis/J.A.R.V.I.S-master/Face-Recognition/trainer/trainer.yml", cascade_path="k:/E.D.I.T.H/extracted_jarvis/J.A.R.V.I.S-master/Face-Recognition/haarcascade_frontalface_default.xml"):
        self.model_path = model_path
        self.cascade_path = cascade_path
        self.names = ['unknown', 'User']  # Map ID to name. User needs to configure this based on training.
        
        # We delay initialization until actual use to prevent overhead and crashes if camera isn't available
        self.recognizer = None
        self.faceCascade = None

    def initialize(self):
        if not os.path.exists(self.model_path):
            return False, "Model file not found."
        if not os.path.exists(self.cascade_path):
            return False, "Cascade file not found."
            
        try:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            self.recognizer.read(self.model_path)
            self.faceCascade = cv2.CascadeClassifier(self.cascade_path)
            return True, "Initialized"
        except Exception as e:
            return False, str(e)

    def identify_face(self, timeout_frames=50):
        """Attempts to identify a face from the webcam within a limited number of frames."""
        success, msg = self.initialize()
        if not success:
            return f"Face Recognition Failed: {msg}"

        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cam.set(3, 640)
        cam.set(4, 480)
        minW = 0.1 * cam.get(3)
        minH = 0.1 * cam.get(4)

        detected_name = "unknown"
        frames_processed = 0

        while frames_processed < timeout_frames:
            ret, img = cam.read()
            if not ret:
                break
                
            converted_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self.faceCascade.detectMultiScale(
                converted_image,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(int(minW), int(minH))
            )

            for (x, y, w, h) in faces:
                id, accuracy = self.recognizer.predict(converted_image[y:y+h, x:x+w])
                
                # < 100 means a match. Closer to 0 is better.
                if accuracy < 100:
                    if id < len(self.names):
                        detected_name = self.names[id]
                    else:
                        detected_name = f"User_ID_{id}"
                    break
            
            if detected_name != "unknown":
                break
                
            frames_processed += 1

        cam.release()
        
        if detected_name != "unknown":
            return f"I see {detected_name}."
        return "I could not identify anyone."
