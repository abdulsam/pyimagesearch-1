# -----------------------------
#   USAGE
# -----------------------------
# python train_camo_detector.py

# -----------------------------
#   IMPORTS
# -----------------------------
# Set the matplotlib backend so figures can be saved in the background
import matplotlib

matplotlib.use("Agg")
# Import the necessary packages
from pyimagesearch import config
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.layers import AveragePooling2D
from tensorflow.keras.layers import Dropout
from tensorflow.keras.layers import Flatten
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import Input
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.applications import ResNet50
from sklearn.metrics import classification_report
from imutils import paths
import matplotlib.pyplot as plt
import numpy as np
import argparse

# Construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--plot", type=str, default="plot.png", help="path to output loss/accuracy plot")
args = vars(ap.parse_args())

# Determine the total number of image paths in training, validation and testing directories
totalTrain = len(list(paths.list_images(config.TRAIN_PATH)))
totalVal = len(list(paths.list_images(config.VAL_PATH)))
totalTest = len(list(paths.list_images(config.TEST_PATH)))

# Initialize the training data augmentation object
trainAug = ImageDataGenerator(rotation_range=25, zoom_range=0.1, width_shift_range=0.1, height_shift_range=0.1,
                              shear_range=0.2, horizontal_flip=True, fill_mode="nearest")

# Initialize the validation/testing data augmentation object (which will be used to add mean subtraction)
valAug = ImageDataGenerator()

# Define the ImageNet mean subtraction (in RGB order) and set the mean subtraction value
# for each of the data augmentation objects
mean = np.array([123.68, 116.779, 103.939], dtype="float32")
trainAug.mean = mean
valAug.mean = mean

# Initialize the training generator
trainGen = trainAug.flow_from_directory(config.TRAIN_PATH, class_mode="categorical", target_size=(224, 224),
                                        color_mode="rgb", shuffle=True, batch_size=config.BS)

# Initialize the validation generator
valGen = valAug.flow_from_directory(config.VAL_PATH, class_mode="categorical", target_size=(224, 224), color_mode="rgb",
                                    shuffle=False, batch_size=config.BS)

# Initialize the testing generator
testGen = valAug.flow_from_directory(config.TEST_PATH, class_mode="categorical", target_size=(224, 224),
                                     color_mode="rgb", shuffle=False, batch_size=config.BS)

# Load the ResNet-50 network, ensuring the head FC layer sets are left off
print("[INFO] Preparing the model...")
baseModel = ResNet50(weights="imagenet", include_top=False, input_tensor=Input(shape=(224, 224, 3)))

# Construct the head of the model that will be placed on top of the base model
headModel = baseModel.output
headModel = AveragePooling2D(pool_size=(7, 7))(headModel)
headModel = Flatten(name="flatten")(headModel)
headModel = Dense(256, activation="relu")(headModel)
headModel = Dropout(0.5)(headModel)
headModel = Dense(len(config.CLASSES), activation="softmax")(headModel)

# Place the head FC model on top of the base model (this will become the actual model that will be used for training)
model = Model(inputs=baseModel.input, outputs=headModel)

# Loop over all layers in the base model and freeze them so they will not be updated during the training process
for layer in baseModel.layers:
    layer.trainable = False

# Compile the model
opt = Adam(lr=config.INIT_LR, decay=config.INIT_LR / config.NUM_EPOCHS)
model.compile(loss="binary_crossentropy", optimizer=opt, metrics=["accuracy"])

# Train the model
print("[INFO] Training the model...")
H = model.fit_generator(trainGen, steps_per_epoch=totalTrain//config.BS, validation_data=valGen,
                        validation_steps=totalVal//config.BS, epochs=config.NUM_EPOCHS)

# Reset the testing generator and then use the trained model to make predictions to the data
print("[INFO] Evaluating the network...")
testGen.reset()
predIdxs = model.predict_generator(testGen, steps=(totalTest//config.BS) + 1)

# For each image in the testing set we need to find the index of the label
# with the corresponding largest predicted probability
predIdxs = np.argmax(predIdxs, axis=1)

# Show a nicely formatted classification report
print(classification_report(testGen.classes, predIdxs, target_names=testGen.class_indices.keys()))

# Serialize the model to disk
print("[INFO] Saving the model...")
model.save(config.MODEL_PATH, save_format="h5")

# Plot the training loss and accuracy
N = config.NUM_EPOCHS
plt.style.use("ggplot")
plt.figure()
plt.plot(np.arange(0, N), H.history["loss"], label="train_loss")
plt.plot(np.arange(0, N), H.history["val_loss"], label="val_loss")
plt.plot(np.arange(0, N), H.history["accuracy"], label="train_acc")
plt.plot(np.arange(0, N), H.history["val_accuracy"], label="val_acc")
plt.title("Training Loss and Accuracy on Dataset")
plt.xlabel("Epoch #")
plt.ylabel("Loss/Accuracy")
plt.legend(loc="lower left")
plt.savefig(args["plot"])
