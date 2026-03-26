def clip(x, low, high):
    return min(high, max(low, x))

def x_left(box):
    return box[0][0]

def x_right(box):
    return box[1][0]

def y_top(box):
    return box[0][1]

def y_bottom(box):
    return box[3][1]
