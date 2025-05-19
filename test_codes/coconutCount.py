import cv2

vid_path = "videos/vid4.mp4"
cap = cv2.VideoCapture(vid_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

#get video properties
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print("FPS: ", fps)
print("video Width: ", width)
print("video Height: ", height)

#define codec and create VideoWriter object
output = cv2.VideoWriter('output.mp4', 
                         cv2.VideoWriter_fourcc(*'mp4v'), 
                         fps, 
                         (width, height))


#ROI coordinates
x1, y1, x2, y2 = 0, 205, 478, 709
roi_height = x2 - x1
roi_width = y2 - y1

#defining trigger line
trigger_line_y = roi_width - 100
print("Trigger line y-coordinate: ", trigger_line_y)

coconut_count = 0

#track coconuts that have already crossed the line
counted_centroids = [] # Stores centroids of counted coconuts
min_distance = 50 # Minimum distance to avoid double-counting

#main loop to process the video stream
while True:
    ret, frame = cap.read() #ret is a boolean value that indicates if the frame was read successfully, frame is the frame itself (as np arr)
    
    if not ret:
        print("End of video reached or an error occured")
        break

    #create ROI (width: 0 to 478, height: 155 to 559)
    roi = frame[y1:y2, x1:x2]

    #draw ROI rectangle on the frame
    # cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    #convert the ROI to HSV for better color thresholding
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    #color ranges to identify coconuts
    lower_brown = (8, 50, 50) #(hue, saturation, value)
    upper_brown = (30, 255, 255)

    #create a mask to isolate brown regions
    mask = cv2.inRange(hsv, lower_brown, upper_brown) #create a binary mask

    #apply mask to the ROI and isolate coconuts
    segmented = cv2.bitwise_and(roi, roi, mask=mask)

    #find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) #returns contours and hierarchy
    #parameters: mask(binary), contour retrieval mode, contour approximation method
    #contuor retrieval modes:
    #cv2.RETR_EXTERNAL: Retrieves only the extreme outer contours.
    #cv2.RETR_LIST: Retrieves all the contours without establishing any hierarchical relationships.
    #cv2.RETR_CCOMP: Retrieves all the contours and organizes them into a two-level hierarchy.
    #cv2.RETR_TREE: Retrieves all the contours and reconstructs a full hierarchy of nested contours.

    #filter contuores by area
    min_area = 2500
    filtered_contours = [c for c in contours if cv2.contourArea(c) > min_area]

    #draw contours on the segmented image
    # frame_with_contours = cv2.drawContours(roi.copy(), filtered_contours, -1, (0, 255, 0), 3)
    #parameters: image, contours, contour index (-1 to draw all contours), color, thickness

    #list to store centroids of coconuts in current frame
    current_centroids = []

    #count the coconuts and draw bounding boxes
    for contour in filtered_contours:
        #  Calculate the centroid of the contour
        M = cv2.moments(contour)

        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            current_centroids.append((cx, cy))

            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(roi, (x, y), (x+w, y+h), (255, 0, 0), 2)


    #check if the coconuts have crossed the trigger line
    for (cx,cy) in current_centroids:
        print(f'centroid: {cx}, {cy} | trigger line y: {trigger_line_y}')
        if cx >= trigger_line_y: #coconut has crossed the line
            #check if the coconut has already been counted
            new_coconut = True
            for (ccx, ccy) in counted_centroids:
                distance = ((ccx - cx)**2 + (ccy - cy)**2)**0.5
                if distance < min_distance:
                    new_coconut = False
                    break

            if new_coconut:
                coconut_count += 1
                counted_centroids.append((cx, cy))

    #draw trigger line
    cv2.line(frame, (trigger_line_y-100, 0), (trigger_line_y-100, height), (0, 0, 255), 2)

    #display the frame
    cv2.putText(frame, f"Coconuts: {coconut_count}", (10, 30),cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.imshow("frame", frame)
    # output.write(frame) #write the frame to the output video

    if cv2.waitKey(0) & 0xFF == ord('q'):
        break

#release the video capture object and close all windows
cap.release()
# output.release() #release the output video object
cv2.destroyAllWindows()