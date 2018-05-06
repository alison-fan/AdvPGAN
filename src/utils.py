import PIL
import numpy as np
import tensorflow as tf
import pickle
import os
import matplotlib.pyplot as plt
import random
from sklearn.preprocessing import OneHotEncoder
from scipy import misc
# import cv2

# change list of labels to one hot encoder
# e.g. [0,1,2] --> [[1,0,0],[0,1,0],[0,0,1]]
def OHE_labels(Y_tr, N_classes):
    OHC = OneHotEncoder()
    Y_ohc = OHC.fit(np.arange(N_classes).reshape(-1, 1))
    Y_labels = Y_ohc.transform(Y_tr.reshape(-1, 1)).toarray()
    return Y_labels

# apply histogram equalization to remove the effect of brightness, use openCV'2 cv2
# scale images between -.5 and .5, by dividing by 255. and subtracting .5.
# this function can be merged with preprocess_image(img, image_size)
def pre_process_image(image):
    # todo Zhanganlan
    # error occurs when cifar-10 is tested
    '''
    image[:,:,0] = cv2.equalizeHist(image[:,:,0])
    image[:,:,1] = cv2.equalizeHist(image[:,:,1])
    image[:,:,2] = cv2.equalizeHist(image[:,:,2])
    '''
    image = image/255. - .5
    return image

def randomly_overlay(image, patch):
    # randomly overlay the image with patch
    patch_mask = np.ones([patch.shape[0],patch.shape[0],3], dtype=np.float32)
    patch_mask = tf.convert_to_tensor(patch_mask)   
    patch_size = int(patch.shape[0])*1.5
    patch = tf.image.resize_image_with_crop_or_pad(patch, int(patch_size), int(patch_size))
    patch_mask = tf.image.resize_image_with_crop_or_pad(patch_mask, int(patch_size), int(patch_size))

    # rotate the patch and mask with the same angle
    angle = np.random.uniform(low=-180.0, high=180.0)
    def random_rotate_image_func(image, angle):
        return misc.imrotate(image, angle, 'bicubic') 
    patch_rotate = tf.py_func(random_rotate_image_func, [patch, angle], tf.uint8)
    patch_mask = tf.py_func(random_rotate_image_func, [patch_mask, angle], tf.uint8)
    patch_rotate = tf.image.convert_image_dtype(patch_rotate, tf.float32)
    patch_mask = tf.image.convert_image_dtype(patch_mask, tf.float32)

    # move the patch and mask to the sama location
    location_x = int(np.random.uniform(low=0, high=int(image.shape[0])-patch_size))
    location_y = int(np.random.uniform(low=0, high=int(image.shape[0])-patch_size))
    patch_rotate = tf.image.pad_to_bounding_box(patch_rotate, location_y, location_x, int(image.shape[0]), int(image.shape[0]))
    patch_mask = tf.image.pad_to_bounding_box(patch_mask, location_y, location_x, int(image.shape[0]), int(image.shape[0]))
        
    # overlay the image with patch
    image_with_patch = (1-patch_mask)*image + patch_rotate
    return image_with_patch

# ZhangAnlan 2018.5.3
# param@num number of image/patch to load
# param@data_dir directory of image/patch
# returnVal@ return a pair of list of image/patch and corresponding labels i.e return image, label
# extra=True --> need to generate extra data, otherwise only preprocess
# N_classes, n_each=, ang_range, shear_range, trans_range and randomize_Var are parameters needed to generate extra data
def load_image(num, file_path, N_classes, encode='latin1'):
    image = []
    label = []
    with open(file_path, 'rb') as f:
        # cifar-10 need use 'latin1'
        data = pickle.load(f, encoding=encode)

    # the names of the keys should be unified as 'data', 'labels'
    # todo Zhanganlan
    # to be removed! liuas test!!!!!!!!
    if str(file_path).endswith("train.p"):
        temp_image = data['features']
    else: # cifar-10 data set needs some pre-process
        temp_image = data['data']
        temp_image = temp_image.reshape(10000, 3, 32, 32).transpose(0, 2, 3, 1).astype("float")
    temp_label = data['labels']

    while(len(label) < num):
        # pick up randomly
        iter = random.randint(0, len(temp_label) - 1)
        image.append(temp_image[iter])
        label.append(temp_label[iter])

    # further tests are needed for ZhangAnlan
    image = np.array([pre_process_image(image[i]) for i in range(len(image))], dtype=np.float32)

    return image, label

# load and augment patch, image with different combinations
def shuffle_augment_and_load(image_num, image_dir, patch_num, patch_dir, batch_size):

    if batch_size <= 0:
        return None

    # load image/patch from directory
    image_set, image_label_set = load_image(image_num, image_dir, N_classes=43)
    patch_set, _ = load_image(patch_num, patch_dir, N_classes=10)

    result_img = []
    result_patch = []
    result_img_label = []

    # all combinations for images and patches
    for i in range(image_num):
        for j in range(patch_num):
            result_img.append(image_set[i])
            #label_tensor = tf.one_hot(image_label_set[i], 43)
            result_img_label.append(image_label_set[i])
            result_patch.append(patch_set[j])

    # more, need to be croped
    if len(result_img) >= batch_size:
        result_img = result_img[:batch_size]
        result_img_label = result_img_label[:batch_size]
        result_patch = result_patch[:batch_size]
        return result_img,result_img_label,result_patch

    # not enough, random pick
    else:
        len_to_supp = batch_size - len(result_img)
        for iter in range(len_to_supp):
            ran_img = random.randint(0, image_num - 1)
            result_img.append(image_set[ran_img])
            #label_tensor = tf.one_hot(image_label_set[ran_img], 43)
            result_img_label.append(image_label_set[ran_img])
            result_patch.append(patch_set[random.randint(0, patch_num - 1)])
        return result_img,result_img_label,result_patch


# preprocess the image
def preprocess_image(img, image_size=128):
    big_dim = max(img.width, img.height)
    wide = img.width > img.height
    new_w = image_size if not wide else int(img.width * image_size / img.height)
    new_h = image_size if wide else int(img.height * image_size / img.width)
    img = img.resize((new_w, new_h)).crop((0, 0, image_size, image_size))
    img = (np.asarray(img) / 255.0).astype(np.float32)
    return img

# load image and corresponding label
def load_data(img_path, image_size=299):
    img = PIL.Image.open(img_path)

    # liuaishan 2018.4.12 for python2.7, remove later
    # img.width = img.size[0]
    # img.height = img.size[1]

    big_dim = max(img.width, img.height)
    wide = img.width > img.height
    new_w = image_size if not wide else int(img.width * image_size / img.height)
    new_h = image_size if wide else int(img.height * image_size / img.width)
    img = img.resize((new_w, new_h)).crop((0, 0, image_size, image_size))
    img = (np.asarray(img) / 255.0).astype(np.float32)

    # todo read label
    y_hat=10
    label = tf.one_hot(y_hat, 1000)
    return img, label

# save tensor
def save_obj(tensor, filename):
    tensor = np.asarray(tensor).astype(np.float32)
    # print(b.eval())
    serialized = pickle.dumps(tensor, protocol=0)
    with open(filename, 'wb') as f:
        f.write(serialized)

# load tensor
def load_obj(filename):
    if os.path.exists(filename):
        return None
    with open(filename, 'rb') as f:
        tensor = pickle.load(f)
    tensor = np.asarray(tensor).astype(np.float32)
    return tensor

def _convert(image):
    return (image * 255.0).astype(np.uint8)

# show image
def show_image(image):
    plt.axis('off')
    plt.imshow(_convert(image), interpolation="nearest")
    plt.show()

