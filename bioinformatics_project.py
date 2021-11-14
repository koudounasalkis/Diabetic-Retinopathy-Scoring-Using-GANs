# -*- coding: utf-8 -*-
"""BioInformatics Project.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1JApw0wVpARVB3BWQBxWWFvTSlCGdSs8-

# Presets

## Import libraries
"""

import tensorflow as tf
import tensorflow_datasets as tfds
import matplotlib.pyplot as plt
import numpy as np
import time
import os
import random

import PIL as pil

from sklearn.linear_model import LinearRegression
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import StratifiedKFold

from IPython import display
from google.colab import drive
drive.mount('/content/gdrive')
gan1, gan2 = None, None

"""## Utils"""

class GAN(tf.keras.Model):
    def __init__(self, discriminator, generator, latent_dim):
        super(GAN, self).__init__()
        self.latent_dim = latent_dim
        self.discriminator = discriminator
        self.generator = generator

    def compile(self, d_optimizer, g_optimizer, loss_fn):
        super(GAN, self).compile()
        self.loss_fn = loss_fn
        self.discriminator_optimizer = d_optimizer
        self.generator_optimizer = g_optimizer

    def train_step(self, images):
        noise = tf.random.normal([batch_size, latent_dim])

        with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
          generated_images = self.generator(noise, training=True)

          real_output = self.discriminator(images, training=True)
          fake_output = self.discriminator(generated_images, training=True)

          gen_loss = self.loss_fn(tf.ones_like(fake_output), fake_output)

          real_loss = self.loss_fn(tf.ones_like(real_output), real_output)
          fake_loss = self.loss_fn(tf.zeros_like(fake_output), fake_output)
          disc_loss = real_loss + fake_loss

        gradients_of_generator = gen_tape.gradient(gen_loss, self.generator.trainable_variables)
        gradients_of_discriminator = disc_tape.gradient(disc_loss, self.discriminator.trainable_variables)

        self.generator_optimizer.apply_gradients(zip(gradients_of_generator, self.generator.trainable_variables))
        self.discriminator_optimizer.apply_gradients(zip(gradients_of_discriminator, self.discriminator.trainable_variables))
        return {"d_loss": disc_loss, "g_loss": gen_loss}

def restore_gan(ver):
  if ver == 1:
    early_stride = (1,1)
    late_stride = (2,2)
    ckpts_path = '/content/gdrive/My Drive/normal_gan_ckpts'
    lr = 0.0001
  elif ver == 2:
    early_stride = (2,2)
    late_stride = (1,1)
    ckpts_path = '/content/gdrive/My Drive/deep_aug_dims_ckpts'
    lr = 0.00001
  else:
    print("Wrong version index")
    return

  discriminator = tf.keras.Sequential(
      [
          tf.keras.layers.InputLayer((512, 512, 3)),

          tf.keras.layers.Conv2D(32, (4, 4), strides=(2, 2), padding='same'),
          tf.keras.layers.LeakyReLU(),
          tf.keras.layers.Dropout(0.3),

          tf.keras.layers.Conv2D(64, (4, 4), strides=(2, 2), padding='same'),
          tf.keras.layers.LeakyReLU(),
          tf.keras.layers.Dropout(0.3),
      
          tf.keras.layers.Conv2D(128, (4, 4), strides=(2, 2), padding='same'),
          tf.keras.layers.LeakyReLU(),
          tf.keras.layers.Dropout(0.3),
      
          tf.keras.layers.Conv2D(256, (4, 4), strides=(2, 2), padding='same'),
          tf.keras.layers.LeakyReLU(),
          tf.keras.layers.Dropout(0.3),
      
          tf.keras.layers.Conv2D(512, (4, 4), strides=(2, 2), padding='same'),
          tf.keras.layers.LeakyReLU(),
          tf.keras.layers.Dropout(0.3),

          tf.keras.layers.Flatten(),
          tf.keras.layers.Dense(1),
      ],
      name="discriminator",
  )
  latent_dim = 100
  generator = tf.keras.Sequential(
      [
          tf.keras.layers.InputLayer(latent_dim),
          tf.keras.layers.Dense(128 * 128 * 128, use_bias=False, input_shape=(100,)),
          tf.keras.layers.BatchNormalization(),
          tf.keras.layers.LeakyReLU(),

          tf.keras.layers.Reshape((128, 128, 128)),
          tf.keras.layers.Conv2DTranspose(64, (4, 4), strides=early_stride, padding='same', use_bias=False),
          tf.keras.layers.BatchNormalization(),
          tf.keras.layers.LeakyReLU(),

          tf.keras.layers.Conv2DTranspose(32, (4, 4), strides=(2, 2), padding='same', use_bias=False),
          tf.keras.layers.BatchNormalization(),
          tf.keras.layers.LeakyReLU(),

          tf.keras.layers.Conv2DTranspose(3, (4, 4), strides=late_stride, padding='same', use_bias=False, activation='sigmoid'),
      ],
      name="generator",
  )
  gan = GAN(discriminator=discriminator, generator=generator, latent_dim=latent_dim)
  gan.compile(
      d_optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
      g_optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
      loss_fn=tf.keras.losses.BinaryCrossentropy(from_logits=True),
  )
  checkpoint = tf.train.Checkpoint(gan)
  checkpoint.restore(tf.train.latest_checkpoint(ckpts_path))
  return gan

def create_extractor(discriminator):
  input = tf.keras.layers.Input(shape=(512, 512, 3))
  extractor = tf.keras.models.Model(discriminator.layers[0].input, discriminator.layers[-3].output)
  extractor.trainable = False
  x = extractor(input)
  x = tf.keras.layers.GlobalAveragePooling2D()(x)
  return tf.keras.models.Model(input, x)

def extract_features(extractor, type='all'):
  dir = "/content/gdrive/MyDrive/dataset"
  ds = tfds.load("diabetic_retinopathy_detection/btgraham-300", data_dir=dir, shuffle_files=True)
  train = ds['train'].map(lambda sample: (tf.image.resize(tf.image.convert_image_dtype(sample['image'], dtype=tf.float32), [512, 512]), tf.cast(sample['label'], tf.float32)))
  test = ds['test'].map(lambda sample: (tf.image.resize(tf.image.convert_image_dtype(sample['image'], dtype=tf.float32), [512, 512]), tf.cast(sample['label'], tf.float32)))

  if type == 'all':
    features = []
    labels = []
    for i, sample in enumerate(train):
      features.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
      labels.append(sample[1])
      print('\rTraining Dataset to list: %.0f%%'%(((i+1)/len(train))*100), end='')
    test_feats = []
    test_labs = []
    for i, sample in enumerate(test):
      test_feats.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
      test_labs.append(sample[1])
      print('\rValidation Dataset to list: %.0f%%'%(((i+1)/len(test))*100), end='')
    return np.array(features), np.array(labels), np.array(test_feats), np.array(test_labs)
  elif type == 'train':
    features = []
    labels = []
    for i, sample in enumerate(train):
      features.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
      labels.append(sample[1])
      print('\rTraining Dataset to list: %.0f%%'%(((i+1)/len(train))*100), end='')
    return np.array(features), np.array(labels)
  else:
    test_feats = []
    test_labs = []
    for i, sample in enumerate(test):
      test_feats.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
      test_labs.append(sample[1])
      print('\rValidation Dataset to list: %.0f%%'%(((i+1)/len(test))*100), end='')
    return np.array(test_feats), np.array(test_labs)

"""# Diabetic Retinopathy Detection Dataset"""

#from google.colab import files
! pip install -q kaggle
# files.upload()
!mkdir -p ~/.kaggle
!cp /content/gdrive/MyDrive/kaggle.json ~/.kaggle/
!chmod 600 ~/.kaggle/kaggle.json
!kaggle datasets download -d prasertsak/dr2015-resized
!unzip -q dr2015-resized.zip -d dr2015-resized
!rm dr2015-resized.zip

!mkdir -p /content/dr2015-resized/manual

!mv /content/dr2015-resized/resized_train/resized_train /content/dr2015-resized/manual/train
!mv /content/dr2015-resized/resized_test/resized_test /content/dr2015-resized/manual/test
!mv /content/dr2015-resized/sampleSubmission.csv /content/dr2015-resized/manual/
!mv /content/dr2015-resized/trainLabels.csv /content/dr2015-resized/manual/

!mkdir -p /content/dr2015-resized/manual/sample

!cp /content/dr2015-resized/manual/train/10003_left.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10003_right.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10007_left.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10007_right.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10009_left.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10009_right.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10010_left.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10010_right.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10013_left.jpeg /content/dr2015-resized/manual/sample/
!cp /content/dr2015-resized/manual/train/10013_right.jpeg /content/dr2015-resized/manual/sample/
builder = tfds.builder(name="diabetic_retinopathy_detection/btgraham-300", data_dir='dr2015-resized')
builder.download_and_prepare(download_dir='dr2015-resized')
!mv /content/dr2015-resized/diabetic_retinopathy_detection /content/diabetic_retinopathy_detection

!zip -r /content/dataset.zip /content/diabetic_retinopathy_detection
files.download('/content/dataset.zip')

"""# Retinopathy Sample Generation

## Load Dataset for GAN Training
"""

# dir = "/content/gdrive/MyDrive/dataset"
# ds = tfds.load("diabetic_retinopathy_detection/btgraham-300", data_dir=dir)
# train_test = ds['train'].concatenate(ds['test'])
# train_test = train_test.map(lambda image: tf.image.resize(tf.image.convert_image_dtype(image['image'], dtype=tf.float32), [512, 512]))
# batch_size = 18
# train_test = train_test.batch(batch_size)

"""## First GAN

### First GAN sample generation

First GAN Discriminator
"""

discriminator = tf.keras.Sequential(
    [
        tf.keras.layers.InputLayer((512, 512, 3)),

        tf.keras.layers.Conv2D(32, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),

        tf.keras.layers.Conv2D(64, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),
     
        tf.keras.layers.Conv2D(128, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),
     
        tf.keras.layers.Conv2D(256, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),
     
        tf.keras.layers.Conv2D(512, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),

        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(1),
    ],
    name="discriminator",
)
discriminator.summary()

"""First GAN Generator"""

latent_dim = 100

generator = tf.keras.Sequential(
    [
        tf.keras.layers.InputLayer(latent_dim),
        tf.keras.layers.Dense(128 * 128 * 128, use_bias=False, input_shape=(100,)),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.LeakyReLU(),

        tf.keras.layers.Reshape((128, 128, 128)),
        tf.keras.layers.Conv2DTranspose(64, (4, 4), strides=(1, 1), padding='same', use_bias=False),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.LeakyReLU(),

        tf.keras.layers.Conv2DTranspose(32, (4, 4), strides=(2, 2), padding='same', use_bias=False),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.LeakyReLU(),

        tf.keras.layers.Conv2DTranspose(3, (4, 4), strides=(2, 2), padding='same', use_bias=False, activation='sigmoid'),
    ],
    name="generator",
)
generator.summary()

"""First GAN Model"""

class GAN(tf.keras.Model):
    def __init__(self, discriminator, generator, latent_dim):
        super(GAN, self).__init__()
        self.latent_dim = latent_dim
        self.discriminator = discriminator
        self.generator = generator

    def compile(self, d_optimizer, g_optimizer, loss_fn):
        super(GAN, self).compile()
        self.loss_fn = loss_fn
        self.discriminator_optimizer = d_optimizer
        self.generator_optimizer = g_optimizer

    def train_step(self, images):
        noise = tf.random.normal([batch_size, latent_dim])

        with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
          generated_images = self.generator(noise, training=True)

          real_output = self.discriminator(images, training=True)
          fake_output = self.discriminator(generated_images, training=True)

          gen_loss = self.loss_fn(tf.ones_like(fake_output), fake_output)

          real_loss = self.loss_fn(tf.ones_like(real_output), real_output)
          fake_loss = self.loss_fn(tf.zeros_like(fake_output), fake_output)
          disc_loss = real_loss + fake_loss

        gradients_of_generator = gen_tape.gradient(gen_loss, self.generator.trainable_variables)
        gradients_of_discriminator = disc_tape.gradient(disc_loss, self.discriminator.trainable_variables)

        self.generator_optimizer.apply_gradients(zip(gradients_of_generator, self.generator.trainable_variables))
        self.discriminator_optimizer.apply_gradients(zip(gradients_of_discriminator, self.discriminator.trainable_variables))
        return {"d_loss": disc_loss, "g_loss": gen_loss}

"""Checkpoint save and restore"""

epochs = 10  # In practice, use ~300 epochs

if gan1 is None:
  gan1 = GAN(discriminator=discriminator, generator=generator, latent_dim=latent_dim)
  gan1.compile(
      d_optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
      g_optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
      loss_fn=tf.keras.losses.BinaryCrossentropy(from_logits=True),
  )

  checkpoint = tf.train.Checkpoint(gan1)
  manager = tf.train.CheckpointManager(checkpoint, '/content/gdrive/My Drive/normal_gan_ckpts', max_to_keep=2)
  checkpoint.restore(tf.train.latest_checkpoint('/content/gdrive/My Drive/normal_gan_ckpts'))

class MyCallback(tf.keras.callbacks.Callback):
 def on_epoch_end(self, epoch, logs=None):
   # manager.save()
   predictions = self.model.generator(tf.random.normal([1, latent_dim]), training=False)
   fig = plt.figure(figsize=(3, 3))
   plt.imshow(predictions[0])
   plt.axis('off')
   plt.show()

"""Plot generated image"""

import plotly.express as px
generatedImage = gan1.generator(tf.random.normal(shape=(1,latent_dim)))
px.imshow(generatedImage[0])

"""### First GAN Training"""

# gan1.fit(train_test, epochs=epochs, callbacks=[MyCallback()])

"""## Second GAN

### Second GAN sample generation

Second GAN Discriminator
"""

discriminator = tf.keras.Sequential(
    [
        tf.keras.layers.InputLayer((512, 512, 3)),

        tf.keras.layers.Conv2D(32, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),

        tf.keras.layers.Conv2D(64, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),
     
        tf.keras.layers.Conv2D(128, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),
     
        tf.keras.layers.Conv2D(256, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),
     
        tf.keras.layers.Conv2D(512, (4, 4), strides=(2, 2), padding='same'),
        tf.keras.layers.LeakyReLU(),
        tf.keras.layers.Dropout(0.3),

        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(1),
    ],
    name="discriminator",
)
discriminator.summary()

"""Second GAN Generator"""

latent_dim = 100

generator = tf.keras.Sequential(
    [
        tf.keras.layers.InputLayer(latent_dim),
        tf.keras.layers.Dense(128 * 128 * 128, use_bias=False, input_shape=(100,)),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.LeakyReLU(),

        tf.keras.layers.Reshape((128, 128, 128)),
        tf.keras.layers.Conv2DTranspose(64, (4, 4), strides=(2, 2), padding='same', use_bias=False),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.LeakyReLU(),

        tf.keras.layers.Conv2DTranspose(32, (4, 4), strides=(2, 2), padding='same', use_bias=False),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.LeakyReLU(),

        tf.keras.layers.Conv2DTranspose(3, (4, 4), strides=(1, 1), padding='same', use_bias=False, activation='sigmoid'),
    ],
    name="generator",
)
generator.summary()

"""Second GAN Model"""

class GAN(tf.keras.Model):
    def __init__(self, discriminator, generator, latent_dim):
        super(GAN, self).__init__()
        self.latent_dim = latent_dim
        self.discriminator = discriminator
        self.generator = generator


    def compile(self, d_optimizer, g_optimizer, loss_fn):
        super(GAN, self).compile()
        self.loss_fn = loss_fn
        self.discriminator_optimizer = d_optimizer
        self.generator_optimizer = g_optimizer

    def train_step(self, images):
        noise = tf.random.normal([batch_size, latent_dim])

        with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
          generated_images = self.generator(noise, training=True)

          real_output = self.discriminator(images, training=True)
          fake_output = self.discriminator(generated_images, training=True)

          gen_loss = self.loss_fn(tf.ones_like(fake_output), fake_output)

          real_loss = self.loss_fn(tf.ones_like(real_output), real_output)
          fake_loss = self.loss_fn(tf.zeros_like(fake_output), fake_output)
          disc_loss = real_loss + fake_loss

        gradients_of_generator = gen_tape.gradient(gen_loss, self.generator.trainable_variables)
        gradients_of_discriminator = disc_tape.gradient(disc_loss, self.discriminator.trainable_variables)

        self.generator_optimizer.apply_gradients(zip(gradients_of_generator, self.generator.trainable_variables))
        self.discriminator_optimizer.apply_gradients(zip(gradients_of_discriminator, self.discriminator.trainable_variables))
        return {"d_loss": disc_loss, "g_loss": gen_loss}

"""Checkpoint save and restore"""

epochs = 10  # In practice, use ~300 epochs

if gan2 is None:
  gan2 = GAN(discriminator=discriminator, generator=generator, latent_dim=latent_dim)
  gan2.compile(
      d_optimizer=tf.keras.optimizers.Adam(learning_rate=0.00001),
      g_optimizer=tf.keras.optimizers.Adam(learning_rate=0.00001),
      loss_fn=tf.keras.losses.BinaryCrossentropy(from_logits=True),
  )

  checkpoint = tf.train.Checkpoint(gan2)
  manager = tf.train.CheckpointManager(checkpoint, '/content/gdrive/My Drive/deep_aug_dims_ckpts', max_to_keep=2)
  checkpoint.restore(tf.train.latest_checkpoint('/content/gdrive/My Drive/deep_aug_dims_ckpts'))

class MyCallback(tf.keras.callbacks.Callback):
 def on_epoch_end(self, epoch, logs=None):
   # manager.save()
   predictions = self.model.generator(tf.random.normal([1, latent_dim]), training=False)
   fig = plt.figure(figsize=(3, 3))
   plt.imshow(predictions[0])
   plt.axis('off')
   plt.show()

"""Plot generated images"""

import plotly.express as px
generatedImage = gan2.generator(tf.random.normal(shape=(1,latent_dim)))
px.imshow(generatedImage[0])

"""### Second GAN Training"""

# gan2.fit(train_test, epochs=epochs, callbacks=[MyCallback()])

"""# Features Extraction

## First GAN Extractor

Extractor build
"""

if gan1 is None: gan1 = restore_gan(1)

input = tf.keras.layers.Input(shape=(512, 512, 3))
extractor = tf.keras.models.Model(gan1.discriminator.layers[0].input, gan1.discriminator.layers[-3].output)
extractor.trainable = False
x = extractor(input)
x = tf.keras.layers.GlobalAveragePooling2D()(x)
extractor = tf.keras.models.Model(input, x)

"""Feature extraction"""

dir = "/content/gdrive/MyDrive/dataset"
ds = tfds.load("diabetic_retinopathy_detection/btgraham-300", data_dir=dir, shuffle_files=True)
train = ds['train'].map(lambda sample: (tf.image.resize(tf.image.convert_image_dtype(sample['image'], dtype=tf.float32), [512, 512]), tf.cast(sample['label'], tf.float32)))
test = ds['test'].map(lambda sample: (tf.image.resize(tf.image.convert_image_dtype(sample['image'], dtype=tf.float32), [512, 512]), tf.cast(sample['label'], tf.float32)))

features = []
labels = []
for i, sample in enumerate(train):
  features.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
  labels.append(sample[1])
  print('\rTraining Dataset to list: %.0f%%'%(((i+1)/len(train))*100), end='')
features = np.array(features)
labels = np.array(labels)

test_feats = []
test_labs = []
for i, sample in enumerate(test):
  test_feats.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
  test_labs.append(sample[1])
  print('\rValidation Dataset to list: %.0f%%'%(((i+1)/len(test))*100), end='')
test_feats = np.array(test_feats)
test_labs = np.array(test_labs)

"""## Second GAN Extractor

Extractor build
"""

if gan2 is None: gan2 = restore_gan(2)

input = tf.keras.layers.Input(shape=(512, 512, 3))
extractor = tf.keras.models.Model(gan2.discriminator.layers[0].input, gan2.discriminator.layers[-3].output)
extractor.trainable = False
x = extractor(input)
x = tf.keras.layers.GlobalAveragePooling2D()(x)
extractor = tf.keras.models.Model(input, x)

"""Features extraction"""

dir = "/content/gdrive/MyDrive/dataset"
ds = tfds.load("diabetic_retinopathy_detection/btgraham-300", data_dir=dir, shuffle_files=True)
train = ds['train'].map(lambda sample: (tf.image.resize(tf.image.convert_image_dtype(sample['image'], dtype=tf.float32), [512, 512]), tf.cast(sample['label'], tf.float32)))
test = ds['test'].map(lambda sample: (tf.image.resize(tf.image.convert_image_dtype(sample['image'], dtype=tf.float32), [512, 512]), tf.cast(sample['label'], tf.float32)))

features = []
labels = []
for i, sample in enumerate(train):
  features.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
  labels.append(sample[1])
  print('\rTraining Dataset to list: %.0f%%'%(((i+1)/len(train))*100), end='')
features = np.array(features)
labels = np.array(labels)

test_feats = []
test_labs = []
for i, sample in enumerate(test):
  test_feats.append(extractor(tf.expand_dims(sample[0], axis=0))[0])
  test_labs.append(sample[1])
  print('\rValidation Dataset to list: %.0f%%'%(((i+1)/len(test))*100), end='')
test_feats = np.array(test_feats)
test_labs = np.array(test_labs)

"""# Cross validation"""

n_folds = 5
if gan2 is None: gan2 = restore_gan(2)
extractor = create_extractor(gan2.discriminator)
features, labels = extract_features(extractor, type='train')
skf = StratifiedKFold(n_folds)

class Regressor(tf.keras.Model):
    def __init__(self, parameters):
        super(Regressor, self).__init__()
        self.parameters = parameters
        self.M = tf.Variable(tf.zeros([self.parameters]), dtype = tf.float32, trainable=True)

    def call(self, val_feats):
        return tf.tensordot(val_feats, self.M, axes=1)

    def compile(self, optimizer):
        super(Regressor, self).compile()
        self.optimizer = optimizer

    def train_on_batch(self, train_samples, train_labs, val_feats, val_labs, weights):

        with tf.GradientTape() as tape:
          labels_pred = tf.tensordot(train_samples, self.M, axes=1)
          train_weights = np.zeros(len(train_labs))
          for i, lab in enumerate(train_labs):
            train_weights[i] = weights[int(lab)]
          loss = tf.reduce_mean(train_weights * tf.square(train_labs - labels_pred))

        grads = tape.gradient(loss, self.trainable_variables)
        self.optimizer.apply_gradients(zip(grads, self.trainable_variables))

        if val_feats is not None and val_labs is not None:
          labels_val = tf.tensordot(val_feats, self.M, axes=1)
          val_weights = np.zeros(len(val_labs))
          for i, lab in enumerate(val_labs):
            val_weights[i] = weights[int(lab)]
          val_loss = mean_squared_error(val_labs, labels_val, sample_weight=val_weights)
          return loss.numpy(), val_loss

        return loss.numpy()

def make_weights(labels, type):
  weights = None
  if type == 'class':
    labels_count = np.zeros(5)
    for l in labels:
      labels_count[int(l)] += 1
    weights = np.zeros(5)
    for i, class_ in enumerate(weights):
      weights[i] = tf.cast(len(labels) / (labels_count[i] * 5), tf.float32)
  elif type == 'sample':
    labels_count = np.zeros(5)
    for l in labels:
      labels_count[int(l)] += 1
    weights = []
    for i, label in enumerate(labels):
      weights.insert(i, tf.cast(len(labels) / (labels_count[int(label)] * 5), tf.float32).numpy())
  else:
    print('Method not found')
  return weights

def train_and_evaluate_model(model_name, train_feats, train_labs, epochs, val_feats, val_labs):

  if model_name == "LR_Analytical_Optimization":
    weights = make_weights(train_labs, 'class')
    start = time.time()
    train_samples = tf.concat([train_feats, np.ones((len(train_feats), 1))], axis=-1)
    val_samples = tf.concat([val_feats, np.ones((len(val_feats), 1))], axis=-1)
    regressor = Regressor(parameters = extractor.output.shape[-1] + 1)
    regressor.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.1))
    for i in range(0, epochs):
      train_loss, val_loss = regressor.train_on_batch(train_samples, train_labs, val_samples, val_labs, weights)
      print('\r\t\tEpoch: %d || train_loss: %f - val_loss: %f'%(i+1, train_loss, val_loss), end='')
    interval = time.time() - start

  elif model_name == "LR_SKlearn":
    c_weights = make_weights(train_labs, 'class')
    weights = make_weights(train_labs, 'sample')
    val_weights = np.zeros(len(val_labs))
    for i, lab in enumerate(val_labs):
      val_weights[i] = c_weights[int(lab)]
      start = time.time()
    reg = LinearRegression()
    reg.fit(train_feats, train_labs, sample_weight=weights)
    preds = reg.predict(val_feats)
    val_loss = mean_squared_error(val_labs, preds, sample_weight=val_weights)
    print('\t\tval_loss: %f'%(val_loss), end='')
    interval = time.time() - start

  elif model_name == "LR_Keras_Dense_Layer":
    weights = make_weights(train_labs, 'class')
    c_w = {0: weights[0], 1: weights[1], 2: weights[2], 3: weights[3], 4: weights[4]}
    val_weights = np.zeros(len(val_labs))
    for i, lab in enumerate(val_labs):
      val_weights[i] = weights[int(lab)]
    start = time.time()
    input = tf.keras.layers.Input(shape=extractor.output.shape[-1])
    output = tf.keras.layers.Dense(units=1)(input)
    regressor = tf.keras.models.Model(input, output)
    regressor.compile(optimizer=tf.optimizers.Adam(learning_rate=0.1), loss='mse')
    for i in range(0, epochs):
      train_loss = regressor.train_on_batch(train_feats, train_labs, class_weight=c_w)
      val_loss = mean_squared_error(val_labs, regressor(val_feats), sample_weight=val_weights)
      print('\r\t\tEpoch: %d || train_loss: %f - val_loss: %f'%(i+1, train_loss, val_loss), end='')
    interval = time.time() - start

  return val_loss, interval

models = ["LR_Analytical_Optimization", "LR_SKlearn", "LR_Keras_Dense_Layer"]

validation_losses = {}
for model_name in models:
  print("Model: %s"%(model_name))
  partial_val_loss = []
  m_interval = 0
  for i, (train_index, test_index) in enumerate(skf.split(features, labels)):
    print("\tFold: %d/%d"%(i+1, n_folds))
    train_feats = features[train_index]
    train_labs = labels[train_index]
    val_feats = features[train_index]
    val_labs = labels[train_index]
    start = time.time()
    val_loss, interval = train_and_evaluate_model(model_name, train_feats, train_labs, 2000, val_feats, val_labs)
    m_interval += interval
    partial_val_loss.append(val_loss)
    print()
  validation_losses[model_name] = (np.mean(partial_val_loss), m_interval/5)
  print()

validation_losses

"""# Linear regression"""

class Regressor(tf.keras.Model):
    def __init__(self, parameters):
        super(Regressor, self).__init__()
        self.parameters = parameters
        self.M = tf.Variable(tf.zeros([self.parameters]), dtype = tf.float32, trainable=True)

    def call(self, val_feats):
        return tf.tensordot(val_feats, self.M, axes=1)

    def compile(self, optimizer):
        super(Regressor, self).compile()
        self.optimizer = optimizer

    def train_on_batch(self, train_samples, train_labs, val_feats, val_labs, weights):

        with tf.GradientTape() as tape:
          labels_pred = tf.tensordot(train_samples, self.M, axes=1)
          train_weights = np.zeros(len(train_labs))
          for i, lab in enumerate(train_labs):
            train_weights[i] = weights[int(lab)]
          loss = tf.reduce_mean(train_weights * tf.square(train_labs - labels_pred))

        grads = tape.gradient(loss, self.trainable_variables)
        self.optimizer.apply_gradients(zip(grads, self.trainable_variables))

        if val_feats is not None and val_labs is not None:
          labels_val = tf.tensordot(val_feats, self.M, axes=1)
          val_weights = np.zeros(len(val_labs))
          for i, lab in enumerate(val_labs):
            val_weights[i] = weights[int(lab)]
          val_loss = mean_squared_error(val_labs, labels_val, sample_weight=val_weights)
          return loss.numpy(), val_loss

        return loss.numpy()

import copy

def make_weights(labels, type):
  weights = None
  if type == 'class':
    labels_count = np.zeros(5)
    for l in labels:
      labels_count[int(l)] += 1
    weights = np.zeros(5)
    for i, class_ in enumerate(weights):
      weights[i] = tf.cast(len(labels) / (labels_count[i] * 5), tf.float32)
  elif type == 'sample':
    labels_count = np.zeros(5)
    for l in labels:
      labels_count[int(l)] += 1
    weights = []
    for i, label in enumerate(labels):
      weights.insert(i, tf.cast(len(labels) / (labels_count[int(label)] * 5), tf.float32).numpy())
  else:
    print('Method not found')
  return weights

def train_and_evaluate_model(model_name, train_feats, train_labs, epochs, val_feats, val_labs):

  if model_name == "LR_Analytical_Optimization":
    evals = []
    weights = make_weights(train_labs, 'class')
    train_samples = tf.concat([train_feats, np.ones((len(train_feats), 1))], axis=-1)
    val_samples = tf.concat([val_feats, np.ones((len(val_feats), 1))], axis=-1)
    regressor = Regressor(parameters = extractor.output.shape[-1] + 1)
    regressor.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.1))
    best_ckpts = {'Model': None, 'val_loss': None}
    eps = []
    for i in range(0, epochs):
      train_loss, val_loss = regressor.train_on_batch(train_samples, train_labs, val_samples, val_labs, weights)
      evals.append(val_loss)
      # train_loss, _ = regressor.train_on_batch(train_samples, train_labs, weights=weights)
      print('\r\t\tEpoch: %d || train_loss: %f - val_loss: %f'%(i+1, train_loss, val_loss), end='')
      if best_ckpts['val_loss'] is None or best_ckpts['val_loss'] > val_loss: 
        eps.append(i)
        best_ckpts = {'Model': copy.copy(regressor), 'val_loss': val_loss}
    print('\r\nSaved best: ', best_ckpts['val_loss'], end='')
    predictions = best_ckpts['Model'](val_samples)
    val_loss = evals

  elif model_name == "LR_SKlearn":
    c_weights = make_weights(train_labs, 'class')
    weights = make_weights(train_labs, 'sample')
    val_weights = np.zeros(len(val_labs))
    for i, lab in enumerate(val_labs):
      val_weights[i] = c_weights[int(lab)]
    reg = LinearRegression()
    reg.fit(train_feats, train_labs, sample_weight=weights)
    predictions = reg.predict(val_feats)
    val_loss = mean_squared_error(val_labs, predictions, sample_weight=val_weights)
    print('\t\tval_loss: %f'%(val_loss), end='')

  return val_loss, predictions

if gan2 is None: gan2 = restore_gan(2)
extractor = create_extractor(gan2.discriminator)
features, labels = extract_features(extractor, type='train')
test_feats, test_labs = extract_features(extractor, type='test')

val_loss_sklearn, pred_sklearn = train_and_evaluate_model("LR_SKlearn", 
                                      features, 
                                      labels, 
                                      10000, 
                                      test_feats, 
                                      test_labs)

val_loss_opt, pred_optimization = train_and_evaluate_model("LR_Analytical_Optimization", 
                                      features, 
                                      labels, 
                                      10000, 
                                      test_feats, 
                                      test_labs)

from sklearn import metrics
import math

for i, (label, pred_skl, pred_opt) in enumerate(zip(test_labs, pred_sklearn, pred_optimization)):
  if i < 30:
    print("GT Label: %d      SKLearn score: %f      Analytical Optimization score: %f"%(label, pred_skl, pred_opt))
  else: break

print("\n\nSKLearn MAE: %f \tAnalytical Optimization MAE: %f"%(metrics.mean_absolute_error(test_labs, pred_sklearn), metrics.mean_absolute_error(test_labs, pred_optimization)))
print("SKLearn RMSE: %f \tAnalytical Optimization RMSE: %f"%(math.sqrt(metrics.mean_squared_error(test_labs, pred_sklearn)), math.sqrt(metrics.mean_squared_error(test_labs, pred_optimization))))