import cv2

def scan_codes():
    # initialize the camera
    cap = cv2.VideoCapture(0)

    list_data = []

    # initialize the QR code detector
    detector = cv2.QRCodeDetector()

    # loop through the video stream
    while True:
        # read a frame from the video stream
        ret, frame = cap.read()

        # detect QR codes in the frame
        data, bbox, _ = detector.detectAndDecode(frame)

        # if a QR code is detected, print the result and exit the loop
        if bbox is not None:
            if data != "" and len(list_data) == 0:
                if input(f"ACCT_NUM? {data}\n") == "y":
                    list_data.append(data)
                    print(list_data)
            elif data != "" and len(list_data) == 1:
                if input(f"C_KEY? {data}\n") == "y":
                    list_data.append(data)
                    print(list_data)
                    break

        # display the frame
        cv2.imshow("QR code reader", frame)

        # exit the loop if the 'q' key is pressed
        if cv2.waitKey(1) == ord("q"):
            break

    # release the camera and close all windows
    cap.release()
    cv2.destroyAllWindows()
    return list_data
