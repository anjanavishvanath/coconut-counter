import cv2

image = cv2.imread('img3.jpg')
hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
cv2.imshow('HSV Image', hsv)
cv2.setMouseCallback('HSV Image', lambda e,x,y,f,p: print(hsv[y, x]) if e == cv2.EVENT_LBUTTONDOWN else None)
cv2.waitKey(0)
cv2.destroyAllWindows()